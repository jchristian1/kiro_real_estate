/**
 * OnboardingWizard — 7-step wizard shell (steps 0–6).
 * Progress bar, step routing, localStorage persistence, back navigation.
 */

import React from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import { useAgentAuth } from '../../contexts/AgentAuthContext';
import { Step0Account } from './Step0Account';
import { Step1Profile } from './Step1Profile';
import { Step2Gmail } from './Step2Gmail';
import { Step3Sources } from './Step3Sources';
import { Step4Automation } from './Step4Automation';
import { Step5Templates } from './Step5Templates';
import { Step6GoLive } from './Step6GoLive';

const STEPS = [
  { path: 'account',    label: 'Account'    },
  { path: 'profile',    label: 'Profile'    },
  { path: 'gmail',      label: 'Gmail'      },
  { path: 'sources',    label: 'Sources'    },
  { path: 'automation', label: 'Automation' },
  { path: 'templates',  label: 'Templates'  },
  { path: 'go-live',    label: 'Go Live'    },
];

export const OnboardingWizard: React.FC = () => {
  const { theme, toggle } = useTheme();
  const t = getTokens(theme);
  const { agent } = useAgentAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Determine current step index from URL
  const seg = location.pathname.split('/').pop() || '';
  const currentStep = STEPS.findIndex(s => s.path === seg);
  const stepIndex = currentStep >= 0 ? currentStep : 0;

  // If agent already completed onboarding, redirect to dashboard
  if (agent?.onboarding_completed) {
    return <Navigate to="/agent/dashboard" replace />;
  }

  const goBack = () => {
    if (stepIndex > 0) navigate(`/agent/onboarding/${STEPS[stepIndex - 1].path}`);
  };

  return (
    <div style={{
      minHeight: '100vh', background: t.bgPage,
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif',
      transition: 'background 0.2s', padding: '0 16px 40px',
      position: 'relative',
    }}>
      {/* Ambient glow */}
      {theme === 'dark' && (
        <div style={{
          position: 'fixed', top: '10%', left: '50%', transform: 'translateX(-50%)',
          width: 600, height: 400, borderRadius: '50%',
          background: 'radial-gradient(ellipse, rgba(99,102,241,0.07) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
      )}

      {/* Theme toggle */}
      <button
        onClick={toggle}
        style={{
          position: 'fixed', top: 20, right: 20,
          background: t.bgCard, border: `1px solid ${t.border}`,
          borderRadius: 20, padding: '6px 14px',
          fontSize: 12, fontWeight: 500, color: t.textMuted,
          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
          zIndex: 10,
        }}
      >
        <span>{theme === 'dark' ? '☀️' : '🌙'}</span>
        {theme === 'dark' ? 'Light' : 'Dark'}
      </button>

      {/* Header */}
      <div style={{ width: '100%', maxWidth: 560, paddingTop: 48, marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 17, color: '#fff', fontWeight: 800,
            boxShadow: '0 4px 12px rgba(99,102,241,0.4)',
          }}>L</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: t.text }}>LeadSync</div>
            <div style={{ fontSize: 10, color: t.textFaint, letterSpacing: '0.6px', textTransform: 'uppercase' }}>Agent Setup</div>
          </div>
        </div>

        {/* Progress bar */}
        <div style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 12, color: t.textMuted }}>
              Step {stepIndex + 1} of {STEPS.length} — {STEPS[stepIndex]?.label}
            </span>
            <span style={{ fontSize: 12, color: t.textFaint }}>
              {Math.round(((stepIndex + 1) / STEPS.length) * 100)}%
            </span>
          </div>
          <div style={{ height: 4, background: t.border, borderRadius: 2, overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 2,
              background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
              width: `${((stepIndex + 1) / STEPS.length) * 100}%`,
              transition: 'width 0.3s ease',
            }} />
          </div>
        </div>

        {/* Step dots */}
        <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
          {STEPS.map((s, i) => (
            <div key={s.path} style={{
              flex: 1, height: 3, borderRadius: 2,
              background: i <= stepIndex ? '#6366f1' : t.border,
              transition: 'background 0.2s',
            }} />
          ))}
        </div>
      </div>

      {/* Step content */}
      <div style={{ width: '100%', maxWidth: 560 }}>
        <Routes>
          <Route index element={<Navigate to="account" replace />} />
          <Route path="account"    element={<Step0Account />} />
          <Route path="profile"    element={<Step1Profile goBack={goBack} />} />
          <Route path="gmail"      element={<Step2Gmail goBack={goBack} />} />
          <Route path="sources"    element={<Step3Sources goBack={goBack} />} />
          <Route path="automation" element={<Step4Automation goBack={goBack} />} />
          <Route path="templates"  element={<Step5Templates goBack={goBack} />} />
          <Route path="go-live"    element={<Step6GoLive goBack={goBack} />} />
          <Route path="*"          element={<Navigate to="account" replace />} />
        </Routes>
      </div>
    </div>
  );
};
