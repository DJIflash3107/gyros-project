import SidebarLayout from "../components/SidebarLayout";

const prepItems = [
  { item: "Pita Bread", needed: 120, prepped: 100, unit: "pcs" },
  { item: "Chicken", needed: 40, prepped: 35, unit: "kg" },
  { item: "Tzatziki", needed: 15, prepped: 10, unit: "L" },
  { item: "Tomatoes", needed: 8, prepped: 8, unit: "kg" },
  { item: "Onions", needed: 6, prepped: 4, unit: "kg" },
];

export default function PrepPlanner() {
  return (
    <SidebarLayout>
      <h2 className="text-2xl font-bold text-blue-950">Prep Planner</h2>
      <p className="mt-1 text-slate-600">Track what needs to be prepared.</p>

      <div className="mt-6 grid gap-4">
        {prepItems.map((p) => {
          const progress = Math.round((p.prepped / p.needed) * 100);
          return (
            <div
              key={p.item}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-blue-950">{p.item}</h3>
                <span className="text-sm font-medium text-slate-600">
                  {p.prepped} / {p.needed} {p.unit}
                </span>
              </div>
              <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-200">
                <div
                  className={`h-full rounded-full ${
                    progress >= 100 ? "bg-emerald-500" : "bg-blue-700"
                  }`}
                  style={{ width: `${Math.min(progress, 100)}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-slate-500">{progress}% complete</p>
            </div>
          );
        })}
      </div>
    </SidebarLayout>
  );
}
