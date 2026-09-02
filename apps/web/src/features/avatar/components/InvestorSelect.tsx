import type { InvestorSummary } from '@loopops/contracts';
import { useTranslation } from '@/i18n';

type InvestorSelectProps = {
  investors: InvestorSummary[];
  selectedId: number | null;
  onSelect: (numeroClienteUnico: number) => void;
  disabled?: boolean;
  loading?: boolean;
};

function optionLabel(
  investor: InvestorSummary,
  format: (key: string, params?: Record<string, string>) => string,
) {
  if (!investor.perfil_riesgo) return investor.nombre_completo;
  return format('live.investor_option', {
    name: investor.nombre_completo,
    risk: investor.perfil_riesgo,
  });
}

/** Demo identity picker: the selected client becomes the JWT subject for the session. */
export function InvestorSelect({
  investors,
  selectedId,
  onSelect,
  disabled = false,
  loading = false,
}: InvestorSelectProps) {
  const { t } = useTranslation();
  if (!loading && investors.length === 0) return null;

  return (
    <label className="flex flex-col gap-1.5">
      <span className="font-heading text-content-small text-xs font-semibold">
        {t('live.investor_label')}
      </span>
      <select
        value={selectedId ?? ''}
        disabled={disabled || loading || investors.length === 0}
        onChange={(event) => onSelect(Number(event.target.value))}
        aria-busy={loading}
        className="border-outline bg-surface text-content focus:border-filled-dark w-full cursor-pointer rounded-xs border px-3 py-2.5 text-sm outline-none disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading && investors.length === 0 ? (
          <option value="">{t('live.investor_loading')}</option>
        ) : (
          investors.map((investor) => (
            <option key={investor.numero_cliente_unico} value={investor.numero_cliente_unico}>
              {optionLabel(investor, t)}
            </option>
          ))
        )}
      </select>
    </label>
  );
}
