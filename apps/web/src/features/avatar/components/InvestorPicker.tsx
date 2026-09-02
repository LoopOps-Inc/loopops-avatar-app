import { useEffect, useState, type ChangeEvent } from 'react';
import type { InvestorSummary } from '@loopops/contracts';
import { useTranslation } from '@/i18n';
import { listInvestors, mintDevToken } from '@/services/advisor-service';
import { clearDevAuth, getDevAuth, setDevAuth } from '@/services/dev-auth';

function formatInvestor(investor: InvestorSummary): string {
  const profile = investor.perfil_riesgo ? ` · ${investor.perfil_riesgo}` : '';
  return `${investor.numero_cliente_unico} · ${investor.nombre_completo}${profile}`;
}

/** Dev-only identity switcher: picks which investor the session acts as. */
export function InvestorPicker() {
  const { t, locale } = useTranslation();
  const [investors, setInvestors] = useState<InvestorSummary[] | null>(null);
  const [selected, setSelected] = useState<string | null>(() => getDevAuth()?.clientId ?? null);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = await listInvestors();
        if (!cancelled) setInvestors(list.investors);
      } catch {
        if (!cancelled) setError(t('live.investor_load_error'));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [locale, t]);

  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const clientId = event.target.value || null;
    setError(null);
    if (!clientId) {
      clearDevAuth();
      setSelected(null);
      return;
    }
    setSelected(clientId);
    setSwitching(true);
    void (async () => {
      try {
        const token = await mintDevToken(clientId);
        setDevAuth({
          clientId: token.client_id,
          accessToken: token.access_token,
          expiresAt: Date.now() + token.expires_in * 1000,
        });
      } catch (err) {
        setSelected(getDevAuth()?.clientId ?? null);
        setError(
          err instanceof Error && err.message ? err.message : t('live.investor_switch_error'),
        );
      } finally {
        setSwitching(false);
      }
    })();
  };

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor="investor-picker" className="text-content-muted text-xs font-medium">
        {t('live.investor_label')}
      </label>
      <select
        id="investor-picker"
        value={selected ?? ''}
        onChange={handleChange}
        disabled={switching || (investors === null && error === null)}
        className="border-outline bg-surface-sub text-content w-full cursor-pointer rounded-xs border px-3 py-2.5 text-sm focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
      >
        <option value="">
          {investors === null && error ? t('live.investor_load_error') : t('live.investor_default')}
        </option>
        {investors?.map((investor) => (
          <option key={investor.id_cliente_pk} value={String(investor.numero_cliente_unico)}>
            {formatInvestor(investor)}
          </option>
        ))}
      </select>
      {error && investors !== null && (
        <p role="alert" className="text-error text-xs">
          {error}
        </p>
      )}
    </div>
  );
}
