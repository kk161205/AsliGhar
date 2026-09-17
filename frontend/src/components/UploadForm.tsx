import { useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";
import type { CreateScanInput } from "../api/client";

// Client-side validation here is a UX convenience only — the backend
// re-validates everything (see backend/app/api/scan.py) and is the source
// of truth for what's actually accepted.
const MIN_PHOTOS = 1;
const MAX_PHOTOS = 5;
const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
const ALLOWED_PHOTO_TYPES = new Set(["image/jpeg", "image/png"]);

interface UploadFormProps {
  onSubmit: (input: CreateScanInput) => void;
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

export default function UploadForm({ onSubmit }: UploadFormProps) {
  const [photos, setPhotos] = useState<File[]>([]);
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [rent, setRent] = useState("");
  const [bhk, setBhk] = useState("");
  const [description, setDescription] = useState("");
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

    setError(null);
    onSubmit({
      photos,
      address: address.trim(),
      city: city.trim(),
      rent: Math.round(rentValue),
      bhk: bhk.trim() || undefined,
      description: description.trim() || undefined,
    });
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      <div
        className={`upload-form__dropzone${isDragging ? " is-dragging" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <p>Drag photos here, or</p>
        <button type="button" onClick={() => fileInputRef.current?.click()}>
          Choose files
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png"
          multiple
          onChange={handleFileInput}
          hidden
          aria-label="Upload listing photos"
        />
        <p className="upload-form__hint">1–5 photos, JPEG or PNG, up to 5MB each</p>
      </div>

      {photos.length > 0 && (
        <ul className="upload-form__thumbnails">
          {photos.map((photo, index) => (
            <li key={`${photo.name}-${photo.lastModified}`}>
              <img src={URL.createObjectURL(photo)} alt={`Listing photo ${index + 1}`} />
              <button type="button" onClick={() => removePhoto(index)} aria-label={`Remove photo ${index + 1}`}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <label className="upload-form__field">
        Address
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
          City
          <input
            type="text"
            value={city}
            onChange={(event) => setCity(event.target.value)}
            placeholder="e.g. Bengaluru"
            required
          />
        </label>
        <label className="upload-form__field">
          Monthly rent
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
          BHK <span className="upload-form__optional">(optional)</span>
          <input
            type="text"
            value={bhk}
            onChange={(event) => setBhk(event.target.value)}
            placeholder="2BHK"
          />
        </label>
      </div>

      <label className="upload-form__field">
        Description <span className="upload-form__optional">(optional)</span>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={3}
          placeholder="Anything else from the listing"
        />
      </label>

      {error && (
        <p className="upload-form__error" role="alert">
          {error}
        </p>
      )}

      <button type="submit" className="upload-form__submit">
        Check this listing
      </button>
    </form>
  );
}
