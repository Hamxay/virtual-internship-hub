import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getPublicPortfolio } from '../../api/portfolio.api';
import PortfolioHero from './PortfolioHero';
import PortfolioProjectCard from './PortfolioProjectCard';

export default function PublicPortfolioPage() {
  const { username } = useParams();
  const [status, setStatus] = useState('loading');
  const [payload, setPayload] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!username) {
        setStatus('notfound');
        return;
      }
      setStatus('loading');
      setPayload(null);
      try {
        const data = await getPublicPortfolio(username);
        if (cancelled) return;
        setPayload(data);
        setStatus('ready');
      } catch (err) {
        if (cancelled) return;
        if (err.response?.status === 404) {
          setStatus('notfound');
        } else {
          setStatus('error');
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [username]);

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4 px-4">
        <div
          className="h-10 w-10 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600"
          aria-hidden
        />
        <p className="text-sm text-slate-600">Loading portfolio…</p>
      </div>
    );
  }

  if (status === 'notfound') {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center px-4 text-center">
        <h1 className="text-2xl font-semibold text-slate-900">Portfolio not found</h1>
        <p className="mt-2 max-w-md text-slate-600">
          We could not find a public portfolio for this link. The student may not exist or has not set up a profile
          yet.
        </p>
        <Link to="/" className="mt-8 text-sm font-semibold text-indigo-600 hover:text-indigo-500">
          Back to home
        </Link>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center px-4 text-center">
        <h1 className="text-2xl font-semibold text-slate-900">Something went wrong</h1>
        <p className="mt-2 max-w-md text-slate-600">Please try again in a moment.</p>
        <Link to="/" className="mt-8 text-sm font-semibold text-indigo-600 hover:text-indigo-500">
          Back to home
        </Link>
      </div>
    );
  }

  const profile = payload?.profile || {};
  const projects = Array.isArray(payload?.top_projects) ? payload.top_projects : [];

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
          <span className="text-sm font-semibold text-slate-800">Virtual Internship Hub</span>
          <Link to="/" className="text-sm font-medium text-indigo-600 hover:text-indigo-500">
            Home
          </Link>
        </div>
      </div>

      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:py-14">
        <PortfolioHero profile={profile} />

        <section className="mt-12">
          <h2 className="text-lg font-semibold text-slate-900">Top mentor-verified projects</h2>
          <p className="mt-1 text-sm text-slate-600">Up to four completed submissions with human review.</p>

          {projects.length === 0 ? (
            <p className="mt-8 rounded-xl border border-dashed border-slate-200 bg-white px-6 py-10 text-center text-slate-600">
              No verified projects to show yet.
            </p>
          ) : (
            <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2">
              {projects.map((project, index) => (
                <PortfolioProjectCard key={project.id ?? index} project={project} />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
