import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Nav from "../components/Nav";
import PasswordInput from "../components/PasswordInput";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate(searchParams.get("next") || "/dashboard", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't log in.");
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <Nav />
      <main className="page page--auth">
        <div className="auth-card">
          <h1>Log in</h1>
          <form className="upload-form" onSubmit={handleSubmit}>
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
                <span className="upload-form__label-text">Password</span>
              </span>
              <PasswordInput
                value={password}
                onChange={setPassword}
                autoComplete="current-password"
                required
              />
            </label>

            {error && (
              <p className="upload-form__error" role="alert">
                {error}
              </p>
            )}

            <button type="submit" className="button-primary" disabled={isSubmitting}>
              {isSubmitting ? "Logging in…" : "Log in"}
            </button>
          </form>
          <p className="auth-card__switch">
            Don't have an account? <Link to="/signup">Sign up</Link>
          </p>
        </div>
      </main>
    </>
  );
}
