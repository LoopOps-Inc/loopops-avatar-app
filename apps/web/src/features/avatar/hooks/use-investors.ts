import { useEffect, useState } from 'react';
import type { InvestorSummary } from '@loopops/contracts';
import { listInvestors } from '@/services/advisor-service';

const STORAGE_KEY = 'loopops.selectedInvestor';

function readStoredId(): number | null {
  if (typeof sessionStorage === 'undefined') return null;
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

export function useInvestors() {
  const [investors, setInvestors] = useState<InvestorSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await listInvestors();
        if (cancelled) return;
        setInvestors(data.investors);
        const stored = readStoredId();
        const match = data.investors.find((investor) => investor.numero_cliente_unico === stored);
        setSelectedId((match ?? data.investors[0])?.numero_cliente_unico ?? null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'investors');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selected =
    investors.find((investor) => investor.numero_cliente_unico === selectedId) ?? null;

  const select = (numeroClienteUnico: number) => {
    setSelectedId(numeroClienteUnico);
    sessionStorage.setItem(STORAGE_KEY, String(numeroClienteUnico));
  };

  return { investors, selected, select, loading, error };
}
