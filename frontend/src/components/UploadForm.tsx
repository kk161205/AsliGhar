import { Plus, X } from "lucide-react";
import { useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";
import type { CreateScanInput } from "../api/client";

// Client-side validation here is a UX convenience only — the backend
// re-validates everything (see backend/app/api/scan.py) and is the source
// of truth for what's actually accepted.
const MIN_PHOTOS = 1;
const MAX_PHOTOS = 5;
const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
const ALLOWED_PHOTO_TYPES = new Set(["image/jpeg", "image/png"]);
const MIN_REASON_CHARS = 10;
const MAX_REASON_CHARS = 300;

// The server asked about this rent; tied to the amount so editing the rent
// afterwards drops the question instead of carrying it to a different figure.
export interface RentConfirmation {
  rent: number;
  message: string;
}

interface UploadFormProps {
  onSubmit: (input: CreateScanInput) => void;
  defaultCity?: string;
  busy?: boolean;
  confirmation?: RentConfirmation | null;
}

// Same rules as the backend (which is the source of truth): an http(s) link,
// and an Indian mobile number that may carry +91 or a leading 0.
function isWebAddress(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}

function normalizeMobile(value: string): string | null {
  const digits = value.replace(/[\s\-().]/g, "").replace(/^(\+?91|0)(?=\d{10}$)/, "");
  return /^[6-9]\d{9}$/.test(digits) ? digits : null;
}

function validatePhotos(photos: File[]): string | null {
  if (photos.length < MIN_PHOTOS || photos.length > MAX_PHOTOS) {
    return `Add between ${MIN_PHOTOS} and ${MAX_PHOTOS} photos.`;
  }
  for (const photo of photos) {
    if (!ALLOWED_PHOTO_TYPES.has(photo.type)) {
      return `${photo.name} isn't a JPEG or PNG.`;
    }
    if (photo.size > MAX_PHOTO_BYTES) {
      return `${photo.name} is over 5MB.`;
    }
  }
  return null;
}

export default function UploadForm({
  onSubmit,
  defaultCity,
  busy = false,
  confirmation = null,
}: UploadFormProps) {
  const [photos, setPhotos] = useState<File[]>([]);
  const [address, setAddress] = useState("");
  const [city, setCity] = useState(defaultCity ?? "");
  const [rent, setRent] = useState("");
  const [bhk, setBhk] = useState("");
  const [description, setDescription] = useState("");
  const [listingUrl, setListingUrl] = useState("");
  const [phone, setPhone] = useState("");
  const [reason, setReason] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function addPhotos(files: FileList | null) {
    if (!files) return;
    setPhotos((current) => [...current, ...Array.from(files)].slice(0, MAX_PHOTOS));
  }

  function removePhoto(index: number) {
    setPhotos((current) => current.filter((_, i) => i !== index));
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    addPhotos(event.dataTransfer.files);
  }

  function handleFileInput(event: ChangeEvent<HTMLInputElement>) {
    addPhotos(event.target.files);
    event.target.value = "";
  }

  const needsReason = confirmation !== null && confirmation.rent === Math.round(Number(rent));

  function handleSubmit(event: FormEvent) {
    event.preventDefault();

    const photoError = validatePhotos(photos);
    if (photoError) {
      setError(photoError);
      return;
    }
    if (!address.trim() || !city.trim()) {
      setError("Address and city are required.");
      return;
    }
    const rentValue = Number(rent);
    if (!rent || !Number.isFinite(rentValue) || rentValue <= 0) {
      setError("Enter a valid monthly rent.");
      return;
    }

    if (listingUrl.trim() && !isWebAddress(listingUrl.trim())) {
      setError("Enter the listing link as a full web address (https://…).");
      return;
    }
    const mobile = phone.trim() ? normalizeMobile(phone) : null;
    if (phone.trim() && mobile === null) {
      setError("Enter a 10-digit mobile number.");
      return;
    }

    if (needsReason && reason.trim().length < MIN_REASON_CHARS) {
      setError(`Say why this rent is right (at least ${MIN_REASON_CHARS} characters).`);
      return;
    }

    setError(null);
    onSubmit({
      photos,
      address: address.trim(),
      city: city.trim(),
      rent: Math.round(rentValue),
      bhk: bhk.trim() || undefined,
      description: description.trim() || undefined,
      listingUrl: listingUrl.trim() || undefined,
      phone: mobile ?? undefined,
      overrideReason: needsReason ? reason.trim() : undefined,
    });
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      <div
        className={`upload-form__dropzone${isDragging ? " is-dragging" : ""}${
          photos.length > 0 ? " has-photos" : ""
        }`}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        {photos.length === 0 ? (
          <>
            <p>Drag photos here, or</p>
            <button type="button" onClick={() => fileInputRef.current?.click()}>
              Choose files
            </button>
            <p className="upload-form__hint">
              1–5 photos, JPEG or PNG, up to 5MB each. Two or more of the same room let us confirm
              a match with certainty, not just a hint.
            </p>
          </>
        ) : (
          <>
            <ul className="upload-form__thumbnails">
              {photos.map((photo, index) => (
                <li key={`${photo.name}-${photo.lastModified}`}>
                  <img src={URL.createObjectURL(photo)} alt={`Listing photo ${index + 1}`} />
                  <button
                    type="button"
                    className="upload-form__thumb-remove"
                    onClick={() => removePhoto(index)}
                    aria-label={`Remove photo ${index + 1}`}
                  >
                    <X size={14} strokeWidth={2.5} />
                  </button>
                </li>
              ))}
              {photos.length < MAX_PHOTOS && (
                <li>
                  <button
                    type="button"
                    className="upload-form__add-more"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Plus size={20} strokeWidth={1.75} />
                    <span>Add</span>
                  </button>
                </li>
              )}
            </ul>
            <p className="upload-form__hint">
              {photos.length} of {MAX_PHOTOS} photos added, JPEG or PNG, up to 5MB each.{" "}
              {photos.length === 1
                ? "Add one more of the same room to confirm a match with certainty."
                : ""}
            </p>
          </>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png"
          multiple
          onChange={handleFileInput}
          hidden
          aria-label="Upload listing photos"
        />
      </div>

      <label className="upload-form__field">
        <span className="upload-form__label-row">
          <span className="upload-form__label-text">Address</span>
        </span>
        <input
          type="text"
          value={address}
          onChange={(event) => setAddress(event.target.value)}
          placeholder="Full address as written in the listing"
          required
        />
      </label>

      <div className="upload-form__row">
        <label className="upload-form__field">
          <span className="upload-form__label-row">
            <span className="upload-form__label-text">City</span>
          </span>
          <input
            type="text"
            value={city}
            onChange={(event) => setCity(event.target.value)}
            placeholder="e.g. Bengaluru"
            required
          />
        </label>
        <label className="upload-form__field">
          <span className="upload-form__label-row">
            <span className="upload-form__label-text">Monthly rent</span>
          </span>
          <div className="upload-form__rent">
            <span aria-hidden="true">₹</span>
            <input
              type="number"
              min={1}
              value={rent}
              onChange={(event) => setRent(event.target.value)}
              placeholder="15000"
              required
            />
          </div>
        </label>
        <label className="upload-form__field">
          <span className="upload-form__label-row">
            <span className="upload-form__label-text">BHK</span>
            <span className="upload-form__optional">Optional</span>
          </span>
          <input
            type="text"
            value={bhk}
            onChange={(event) => setBhk(event.target.value)}
            placeholder="2BHK"
          />
        </label>
      </div>

      <div className="upload-form__row upload-form__row--two">
        <label className="upload-form__field">
          <span className="upload-form__label-row">
            <span className="upload-form__label-text">Listing link</span>
            <span className="upload-form__optional">Optional</span>
          </span>
          <input
            type="url"
            value={listingUrl}
            onChange={(event) => setListingUrl(event.target.value)}
            placeholder="https://…"
          />
        </label>
        <label className="upload-form__field">
          <span className="upload-form__label-row">
            <span className="upload-form__label-text">Contact number</span>
            <span className="upload-form__optional">Optional</span>
          </span>
          <input
            type="tel"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            placeholder="98765 43210"
          />
        </label>
      </div>
      <p className="upload-form__hint">
        A link lets us read the listing itself; a number lets us look for it on other listings.
      </p>

      <label className="upload-form__field">
        <span className="upload-form__label-row">
          <span className="upload-form__label-text">Description</span>
          <span className="upload-form__optional">Optional</span>
        </span>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={3}
          placeholder="Anything else from the listing"
        />
      </label>

      {needsReason && (
        <div className="upload-form__confirm" role="group" aria-label="Confirm this rent">
          <p className="upload-form__confirm-message">{confirmation.message}</p>
          <label className="upload-form__field">
            <span className="upload-form__label-row">
              <span className="upload-form__label-text">Why is this rent right?</span>
            </span>
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={2}
              maxLength={MAX_REASON_CHARS}
              placeholder="e.g. a single room in a family home"
              autoFocus
            />
          </label>
          <p className="upload-form__hint">
            Shown next to the result. It doesn't change the score.
          </p>
        </div>
      )}

      {error && (
        <p className="upload-form__error" role="alert">
          {error}
        </p>
      )}

      <button type="submit" className="button-primary upload-form__submit" disabled={busy}>
        {needsReason ? "Scan anyway" : "Check this listing"}
      </button>
    </form>
  );
}
