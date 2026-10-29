import { useEffect, useState } from "react";
import { api } from "../api.js";
import Card from "../components/Card.jsx";

const fmt = (v) => v.toFixed(3);

export default function ModelPage() {
  const [info, setInfo] = useState(null);

  useEffect(() => {
    api("/model-info").then(setInfo);
  }, []);

  if (!info) return <p className="text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6">
      <Card title="Model performance on held-out shipments">
        <p className="mb-4 text-sm text-slate-500">
          {info.test_set.split}. The test set has {info.test_set.shipments} shipments, of which {info.test_set.late} (
          {(info.test_set.late_share * 100).toFixed(1)}%) were late.
        </p>
        <p className="mb-4 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
          Recall depends on how many shipments are flagged, so compare models at equal review capacity: the last column
          shows the share of late shipments caught when only the 20% highest-risk shipments are reviewed, and how many times
          better that is than reviewing at random.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <th className="py-2 pr-3">Model</th>
                <th className="py-2 pr-3">ROC-AUC</th>
                <th className="py-2 pr-3">PR-AUC</th>
                <th className="py-2 pr-6">Top 20%: caught / lift</th>
                <th className="py-2 pr-3 text-slate-400">Precision*</th>
                <th className="py-2 pr-3 text-slate-400">Recall*</th>
                <th className="py-2 pr-3 text-slate-400">F1*</th>
                <th className="py-2 pr-3 text-slate-400">F2*</th>
                <th className="py-2 text-slate-400">Flagged*</th>
              </tr>
            </thead>
            <tbody>
              {info.models.map((m) => (
                <tr key={m.name} className="border-b border-slate-100">
                  <td className="py-2 pr-3 font-medium text-slate-800">{m.name}{m.name === info.final_model ? <span className="ml-2 rounded bg-brand-100 px-1.5 text-xs text-brand-700">used in app</span> : null}</td>
                  <td className="py-2 pr-3">{fmt(m.roc_auc)}</td>
                  <td className="py-2 pr-3">{m.pr_auc == null ? "-" : fmt(m.pr_auc)}</td>
                  <td className="py-2 pr-6 font-semibold text-brand-700">
                    {m.top20_recall == null ? "-" : `${(m.top20_recall * 100).toFixed(0)}% / ${m.lift20.toFixed(1)}x`}
                  </td>
                  <td className="py-2 pr-3 text-slate-400">{fmt(m.precision)}</td>
                  <td className="py-2 pr-3 text-slate-400">{fmt(m.recall)}</td>
                  <td className="py-2 pr-3 text-slate-400">{fmt(m.f1)}</td>
                  <td className="py-2 pr-3 text-slate-400">{fmt(m.f2)}</td>
                  <td className="py-2 text-slate-400">{m.flagged_share == null ? "-" : (m.flagged_share * 100).toFixed(0) + "%"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-slate-400">
          * Measured at a threshold chosen to catch about 80% of late shipments in validation. It flags most shipments, so compare models on the first three metrics instead.
        </p>
      </Card>

      <Card title="Risk bands">
        {info.thresholds.data_driven ? (
          <p className="text-sm text-slate-600">
            Low is a model score below {info.thresholds.medium.toFixed(2)}, Medium is {info.thresholds.medium.toFixed(2)} to{" "}
            {info.thresholds.high.toFixed(2)}, High is {info.thresholds.high.toFixed(2)} and above. {info.thresholds.rule}
          </p>
        ) : (
          <p className="text-sm text-slate-600">
            Default cut-offs (30% and 50%) are in use because the model file is not loaded.
          </p>
        )}
        <p className="mt-2 text-xs text-slate-400">
          Feature set: {info.feature_set}. Probabilities are {info.calibrated ? "calibrated" : "not calibrated"}. Metrics source: {info.from_notebook ? "exported from the training notebook (models/initial_metrics.csv)" : "reference values from the notebook run (copy initial_metrics.csv into app/models to load them live)"}.
        </p>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="How to read this">
          <ul className="space-y-2 text-sm text-slate-600">
            <li><strong>Recall</strong> is the share of truly late shipments the model catches. It is the priority metric because a missed delay can interrupt treatment.</li>
            <li><strong>Precision</strong> is the share of flagged shipments that really were late. It is low at the high-recall threshold, so many alerts are false alarms.</li>
            <li><strong>F2</strong> weights recall more than precision. <strong>ROC-AUC</strong> measures how well risk scores rank late above on-time shipments.</li>
          </ul>
        </Card>
        <Card title="Limitations">
          <ul className="space-y-2 text-sm text-slate-600">
            {!info.calibrated && <li>Risk scores are relative: they are not calibrated probabilities.</li>}
            <li>With about {info.test_set.late} late shipments in the test set, results have wide uncertainty (see the confidence interval in the notebook).</li>
            <li>The data covers 2006 to 2015, so this is a proof of concept.</li>
            <li>Only about 286 shipments in total were late, so results on the small test set are noisy.</li>
            <li>The machine-learning models perform about the same as the simple vendor-recency rule (the confidence intervals overlap). Their added value is calibrated probabilities, per-shipment explanations and a framework that can learn from real clinic data.</li>
            <li>The shipment data record only the destination country, so a district inherits its country's predicted risk; district detail comes only from reports.</li>
            <li>Sign-in and roles are basic: there is no password reset, email verification or two-factor sign-in yet.</li>
            <li>Model status: {info.model_loaded ? `${info.final_model} loaded.` : "model file not loaded, using fallback scoring."}</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
