import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Nav from "../components/Nav";
import PasswordInput from "../components/PasswordInput";

const MIN_PASSWORD_LENGTH = 8;

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [city, setCity] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await signup({ email, password, fullName, city });
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create an account.");
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <Nav />
      <main className="page page--auth">
        <div className="auth-card">
          <h1>Sign up</h1>
          <form className="upload-form" onSubmit={handleSubmit}>
            <label className="upload-form__field">
              <span className="upload-form__label-row">
                <span className="upload-form__label-text">Full name</span>
              </span>
              <input
                type="text"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="As you'd like it shown on your dashboard"
                autoComplete="name"
                required
              />
            </label>

            <label className="upload-form__field">
              <span className="upload-form__label-row">
                <span className="upload-form__label-text">Email</span>
              </span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                required
              />
            </label>

            <label className="upload-form__field">
              <span className="upload-form__label-row">
                <span className="upload-form__label-text">City</span>
              </span>
              <input
                type="text"
                value={city}
                onChange={(event) => setCity(event.target.value)}
                placeholder="e.g. Bengaluru — helps prefill your scans"
                autoComplete="address-level2"
                required
              />
            </label>

            <label className="upload-form__field">
              <span className="upload-form__label-row">
                <span className="upload-form__label-text">Password</span>
              </span>
              <PasswordInput
                value={password}
                onChange={setPassword}
                autoComplete="new-password"
                minLength={MIN_PASSWORD_LENGTH}
                required
              />
              <p className="upload-form__hint">At least {MIN_PASSWORD_LENGTH} characters.</p>
            </label>

            {error && (
              <p className="upload-form__error" role="alert">
                {error}
              </p>
            )}

            <button type="submit" className="button-primary" disabled={isSubmitting}>
              {isSubmitting ? "Creating account…" : "Sign up"}
            </button>
          </form>
          <p className="auth-card__switch">
            Already have an account? <Link to="/login">Log in</Link>
          </p>
        </div>
      </main>
    </>
  );
}
