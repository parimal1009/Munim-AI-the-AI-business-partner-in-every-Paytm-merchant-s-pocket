import { useMutation, useQuery } from "@tanstack/react-query";
import { Store } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Button, Card, ErrorState, Spinner } from "../components/ui";

export default function Login() {
  const { login } = useAuth();
  const merchants = useQuery({ queryKey: ["merchants"], queryFn: api.merchants });
  const go = useMutation({ mutationFn: (id: number) => login(id) });
  return (
    <div className="grid min-h-screen place-items-center bg-gradient-to-br from-paytm-navy to-sky-700 p-5">
      <Card className="w-full max-w-md">
        <div className="mb-5 text-center">
          <div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-paytm-blue text-2xl font-bold text-white">म</div>
          <h1 className="text-2xl font-bold text-paytm-navy">Munim AI</h1>
          <p className="text-slate-500">Har dukaan ka apna AI Munim</p>
        </div>
        <p className="mb-3 text-sm font-medium text-slate-600">Demo login: choose a Paytm merchant</p>
        {merchants.isLoading && <Spinner />}
        {merchants.error && <ErrorState error={merchants.error} retry={() => merchants.refetch()} />}
        <div className="space-y-2">
          {merchants.data?.map((m) => (
            <Button key={m.id} variant="ghost" className="w-full justify-start py-3" busy={go.isPending && go.variables === m.id} onClick={() => go.mutate(m.id)}>
              <Store className="h-4 w-4" />
              <span className="text-left"><b>{m.name}</b><br /><span className="font-normal text-slate-500">{m.city}</span></span>
            </Button>
          ))}
        </div>
        {go.error && <div className="mt-3"><ErrorState error={go.error} /></div>}
      </Card>
    </div>
  );
}
