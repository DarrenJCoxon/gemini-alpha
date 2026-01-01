import { LoginForm } from '@/components/auth/login-form';
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Login | ContrarianAI',
  description: 'Access your ContrarianAI Mission Control',
};

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-zinc-100">ContrarianAI</h1>
          <p className="text-zinc-400 mt-2">Mission Control Access</p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
