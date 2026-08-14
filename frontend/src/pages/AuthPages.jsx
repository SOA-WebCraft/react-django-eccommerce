import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { authApi } from '../api/services';
import { ApiError, fieldErrors } from '../api/client';
import { Alert, Button, Field } from '../components/ui';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import { FcGoogle } from 'react-icons/fc';
import { FaApple, FaFacebookF, FaLinkedinIn } from 'react-icons/fa';
import { FiLock, FiPackage, FiRefreshCw } from 'react-icons/fi';
export function LoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const { login } = useAuth();
    const { notify } = useToast();
    const location = useLocation();
    const navigate = useNavigate();
    const from = location.state?.from || '/account';
    const submit = async (event) => {
        event.preventDefault();
        setError('');
        if (!username.trim() || !password) {
            setError('Enter your username and password to continue.');
            return;
        }
        setLoading(true);
        try {
            const authenticatedUser = await login(username.trim(), password);
            notify('Welcome back.', 'success');
            const destination = authenticatedUser.can_manage_orders || authenticatedUser.can_manage_catalog ? '/' : from;
            navigate(destination, { replace: true });
        }
        catch (reason) {
            const message = reason instanceof Error ? reason.message : 'Unable to sign in.';
            setError(message);
            if (!(reason instanceof ApiError))
                notify(message, 'error');
        }
        finally {
            setLoading(false);
        }
    };
    return <AuthShell title="Welcome back" intro="Sign in to continue to your account and orders.">
    <SocialLoginButtons next={from}/>
    <div className="auth-divider"><span>or sign in with your account</span></div>
    {error && <Alert>{error}</Alert>}
    <form onSubmit={submit} className="auth-form" autoComplete="off">
      <Field label="Username" name="login_username" autoComplete="off" placeholder="Enter your username" required value={username} onChange={(e) => setUsername(e.target.value)}/>
      <div className="auth-password-heading"><span>Password</span><Link to="/forgot-password">Forgot password?</Link></div>
      <Field label={<span className="sr-only">Password</span>} name="login_password" type="password" autoComplete="off" placeholder="Enter your password" required value={password} onChange={(e) => setPassword(e.target.value)}/>
      <Button type="submit" className="button--wide" disabled={loading}>{loading ? 'Signing in…' : 'Sign in securely'}</Button>
    </form>
    <p className="auth-switch">New to ECCO? <Link to="/register">Create an account</Link></p>
  </AuthShell>;
}
export function RegisterPage() {
    const [form, setForm] = useState({ username: '', email: '', password: '', confirm: '' });
    const [loading, setLoading] = useState(false);
    const { notify } = useToast();
    const navigate = useNavigate();
    const submit = async (event) => {
        event.preventDefault();
        const validation = {};
        if (form.username.trim().length < 3)
            validation.username = 'Use at least 3 characters.';
        if (!form.email.includes('@'))
            validation.email = 'Enter a valid email address.';
        if (form.password.length < 8)
            validation.password = 'Use at least 8 characters.';
        if (form.password !== form.confirm)
            validation.confirm = 'Passwords do not match.';
        if (Object.keys(validation).length) {
            Object.entries(validation).forEach(([field, message]) => notify(`${field}: ${message}`, 'error'));
            return;
        }
        setLoading(true);
        try {
            await authApi.register({ username: form.username.trim(), email: form.email.trim(), password: form.password });
            notify('Account created. Sign in to continue.', 'success');
            navigate('/login');
        }
        catch (reason) {
            if (!(reason instanceof ApiError)) {
                notify('Unable to create your account.', 'error');
            }
        }
        finally {
            setLoading(false);
        }
    };
    return <AuthShell title="Create your account" intro="Save your cart and keep every order in one place.">
    <form onSubmit={submit} className="auth-form">
      <Field label="Username" name="username" autoComplete="username" required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })}/>
      <Field label="Email address" name="email" type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}/>
      <Field label="Password" name="password" type="password" autoComplete="new-password" required hint="Use at least 8 characters and avoid common passwords." value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}/>
      <Field label="Confirm password" name="confirm" type="password" autoComplete="new-password" required value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })}/>
      <Button type="submit" disabled={loading}>{loading ? 'Creating account…' : 'Create account'}</Button>
    </form>
    <SocialLoginButtons next="/account"/>
    <p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></p>
  </AuthShell>;
}

function SocialLoginButtons({ next }) {
    const [providers, setProviders] = useState([]);
    useEffect(() => {
        authApi.socialProviders().then((data) => setProviders(data.results || [])).catch(() => setProviders([]));
    }, []);
    const enabled = providers.filter((provider) => provider.enabled);
    if (!enabled.length)
        return null;
    const icons = { google: <FcGoogle/>, apple: <FaApple/>, facebook: <FaFacebookF/>, linkedin: <FaLinkedinIn/> };
    return <div className="social-login" aria-label="Social sign in">
      <div className="social-login__grid">
        {enabled.map((provider) => <a className={`social-button social-button--${provider.provider}`} href={authApi.socialLoginUrl(provider.provider, next)} key={provider.provider}>
          <span aria-hidden="true">{icons[provider.provider]}</span>
          Continue with {provider.label}
        </a>)}
      </div>
    </div>;
}

export function SocialAuthCallbackPage() {
    const { restoreSession } = useAuth();
    const { notify } = useToast();
    const location = useLocation();
    const navigate = useNavigate();
    useEffect(() => {
        const params = new URLSearchParams(location.search);
        if (params.get('status') !== 'success') {
            notify(params.get('message') || 'Social sign-in could not be completed.', 'error');
            navigate('/login', { replace: true });
            return;
        }
        restoreSession().then(() => {
            notify('Welcome. You are signed in.', 'success');
            navigate(params.get('next') || '/account', { replace: true });
        }).catch(() => {
            notify('The sign-in session could not be restored.', 'error');
            navigate('/login', { replace: true });
        });
    }, [location.search, navigate, notify, restoreSession]);
    return <AuthShell title="Finishing sign in" intro="Securely connecting your account…"><div className="loader" role="status">Signing you in…</div></AuthShell>;
}
export function ForgotPasswordPage() {
    const [email, setEmail] = useState('');
    const [loading, setLoading] = useState(false);
    const [submitted, setSubmitted] = useState(false);
    const [error, setError] = useState('');
    const submit = async (event) => {
        event.preventDefault();
        setError('');
        if (!email.includes('@')) {
            setError('Enter a valid email address.');
            return;
        }
        setLoading(true);
        try {
            await authApi.requestPasswordReset(email.trim());
            setSubmitted(true);
        }
        catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Unable to request a reset link.');
        }
        finally { setLoading(false); }
    };
    return <AuthShell title="Reset your password" intro="Enter the email address associated with your account.">
      {submitted ? <><Alert kind="success">If an active account exists for that email address, a reset link has been sent. Check your inbox and spam folder.</Alert><p className="auth-switch"><Link to="/login">Return to sign in</Link></p></> : <form onSubmit={submit} className="auth-form">
        <Field label="Email address" name="email" type="email" autoComplete="email" required value={email} error={error} onChange={(event) => setEmail(event.target.value)}/>
        <Button type="submit" disabled={loading}>{loading ? 'Sending…' : 'Send reset link'}</Button>
      </form>}
    </AuthShell>;
}

export function ResetPasswordPage() {
    const { uid = '', token = '' } = useParams();
    const [form, setForm] = useState({ new_password: '', confirm_password: '' });
    const [errors, setErrors] = useState({});
    const [loading, setLoading] = useState(false);
    const { notify } = useToast();
    const navigate = useNavigate();
    const submit = async (event) => {
        event.preventDefault();
        const validation = {};
        if (form.new_password.length < 8)
            validation.new_password = 'Use at least 8 characters.';
        if (form.new_password !== form.confirm_password)
            validation.confirm_password = 'Passwords do not match.';
        if (Object.keys(validation).length) {
            setErrors(validation);
            return;
        }
        setErrors({});
        setLoading(true);
        try {
            await authApi.confirmPasswordReset({ uid, token, ...form });
            notify('Password reset successfully. Sign in with your new password.', 'success');
            navigate('/login', { replace: true });
        }
        catch (reason) {
            if (reason instanceof ApiError)
                setErrors(fieldErrors(reason.data));
            else
                setErrors({ token: 'Unable to reset your password.' });
        }
        finally { setLoading(false); }
    };
    return <AuthShell title="Choose a new password" intro="Create a strong password you have not used before.">
      {errors.token && <Alert>{errors.token}</Alert>}
      <form onSubmit={submit} className="auth-form">
        <Field label="New password" name="new_password" type="password" autoComplete="new-password" required hint="Use at least 8 characters and avoid common passwords." value={form.new_password} error={errors.new_password} onChange={(event) => setForm({ ...form, new_password: event.target.value })}/>
        <Field label="Confirm new password" name="confirm_password" type="password" autoComplete="new-password" required value={form.confirm_password} error={errors.confirm_password} onChange={(event) => setForm({ ...form, confirm_password: event.target.value })}/>
        <Button type="submit" disabled={loading}>{loading ? 'Resetting…' : 'Reset password'}</Button>
      </form>
      <p className="auth-switch"><Link to="/forgot-password">Request another reset link</Link></p>
    </AuthShell>;
}

function AuthShell({ title, intro, children }) {
    return <main className="auth-page"><section className="auth-panel"><Link className="brand auth-brand" to="/">ECCO<span>.</span></Link><div className="auth-panel__heading"><p className="eyebrow">Your ECCO account</p><h1>{title}</h1><p>{intro}</p></div>{children}<p className="session-note"><FiLock aria-hidden="true"/> Secure, encrypted account access</p></section><aside className="auth-visual" aria-label="ECCO shopping benefits"><div className="auth-visual__glow"/><div className="auth-visual__content"><span className="auth-visual__badge">ECCO MEMBER</span><p className="eyebrow">Everything in one place</p><h2>Shop smarter.<br />Stay connected.</h2><p>Save your cart, follow every delivery, and access member-only offers from any device.</p><ul><li><FiPackage/><span><strong>Track every order</strong><small>Live status from checkout to delivery</small></span></li><li><FiRefreshCw/><span><strong>Faster repeat purchases</strong><small>Your profile and order history, ready</small></span></li><li><FiLock/><span><strong>Protected checkout</strong><small>Secure provider-hosted payments</small></span></li></ul></div></aside></main>;
}
