import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getPublicPortfolio } from '../../api/portfolio.api';
import { resolvePortfolioDisplay } from '../../utils/portfolioDisplay';
import { downloadElementAsPdf } from '../../utils/portfolioPdfExport';
import PortfolioHero from './PortfolioHero';
import PortfolioProjectCard from './PortfolioProjectCard';

export default function PublicPortfolioPage() {
  const { username } = useParams();
  const [status, setStatus] = useState('loading');
  const [payload, setPayload] = useState(null);
  const [exporting, setExporting] = useState(false);
  const exportRootRef = useRef(null);

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

  const handleDownloadPdf = useCallback(async () => {
    const el = exportRootRef.current;
    if (!el) return;
    setExporting(true);
    try {
      const view = resolvePortfolioDisplay(payload?.profile || {}, username);
      const base = `${view.slugBase}-portfolio`;
      await downloadElementAsPdf(el, base);
    } catch (e) {
      // eslint-disable-next-line no-alert
      window.alert(
        e?.message?.includes('Nothing to export')
          ? 'Unable to export this page.'
          : 'Could not create the PDF. If the problem continues, use Print → Save as PDF in your browser.',
      );
    } finally {
      setExporting(false);
    }
  }, [payload, username]);

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-white px-4">
        <div
          className="h-9 w-9 animate-spin rounded-full border-2 border-slate-200 border-t-slate-600"
          aria-hidden
        />
        <p className="text-sm text-slate-600">Loading portfolio…</p>
      </div>
    );
  }

  if (status === 'notfound') {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-white px-4 text-center">
        <h1 className="text-xl font-semibold text-slate-900">Portfolio not found</h1>
        <p className="mt-2 max-w-md text-sm text-slate-600">
          We could not find a public portfolio for this link. The student may not exist or has not set up a profile
          yet.
        </p>
        <Link to="/" className="mt-8 text-sm font-medium text-slate-900 underline underline-offset-4 hover:text-slate-700">
          Back to home
        </Link>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-white px-4 text-center">
        <h1 className="text-xl font-semibold text-slate-900">Something went wrong</h1>
        <p className="mt-2 max-w-md text-sm text-slate-600">Please try again in a moment.</p>
        <Link to="/" className="mt-8 text-sm font-medium text-slate-900 underline underline-offset-4 hover:text-slate-700">
          Back to home
        </Link>
      </div>
    );
  }

  const profile = payload?.profile || {};
  const portfolioView = resolvePortfolioDisplay(profile, username);
  const projects = Array.isArray(payload?.top_projects) ? payload.top_projects : [];
  const exportFileHint = `${portfolioView.displayName} — portfolio PDF`;

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-100 via-cyan-50 to-emerald-50/60 text-slate-900">
      <header className="sticky top-0 z-10 border-b border-cyan-300 bg-gradient-to-r from-cyan-500 via-teal-500 to-sky-500 backdrop-blur-sm">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <span className="text-sm font-semibold text-white">Virtual Internship Hub</span>
          <div className="flex items-center gap-3 sm:gap-4">
            <button
              type="button"
              onClick={handleDownloadPdf}
              disabled={exporting}
              aria-busy={exporting}
              title={exportFileHint}
              className="rounded-md border border-white/60 bg-white/90 px-3 py-1.5 text-sm font-medium text-teal-700 shadow-sm transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {exporting ? 'Preparing…' : 'Download PDF'}
            </button>
            <Link
              to="/"
              className="text-sm font-medium text-white/95 underline-offset-4 hover:text-white hover:underline"
            >
              Home
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-12">
        <div
          ref={exportRootRef}
          className="portfolio-pdf-export-root rounded-2xl border border-cyan-200 bg-white px-5 py-8 shadow-lg shadow-cyan-200/50 sm:px-8 sm:py-10"
        >
          <PortfolioHero
            displayName={portfolioView.displayName}
            domains={portfolioView.domains}
            bio={portfolioView.bio}
          />

          <section className="mt-10 rounded-xl border border-cyan-200 bg-gradient-to-r from-cyan-100/70 via-sky-50 to-teal-100/60 p-5 sm:p-6">
            <h2 className="text-base font-semibold text-cyan-950">Verified projects</h2>
            <p className="mt-1 text-sm text-slate-600">Completed work with mentor review (up to four).</p>

            {projects.length === 0 ? (
              <article className="mt-8 rounded-lg border border-sky-200 bg-white px-5 py-6 shadow-sm shadow-cyan-100/40 sm:px-6">
                <h3 className="text-sm font-semibold text-cyan-950">Project showcase</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">
                  This area will list up to four mentor-verified projects with evaluation scores and feedback once you
                  complete work and it is reviewed. Share your profile link anytime—visitors will see your story above
                  and your verified projects as they are added.
                </p>
              </article>
            ) : (
              <div className="mt-8 flex flex-col gap-6">
                {projects.map((project, index) => (
                  <PortfolioProjectCard key={project.id ?? index} project={project} />
                ))}
              </div>
            )}

            <p className="mt-8 text-center text-[11px] text-slate-500">
              Virtual Internship Hub — public portfolio
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
