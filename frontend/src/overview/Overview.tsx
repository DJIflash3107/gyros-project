import SidebarLayout from "../components/SidebarLayout";

const stats = [
  { label: "Today's Orders", value: 142 },
  { label: "Revenue", value: "$3,240" },
  { label: "Items Prepped", value: 89 },
  { label: "Pending Prep", value: 12 },
];

export default function Overview() {
  return (
    <SidebarLayout>
      <h2 className="text-2xl font-bold text-blue-950">Overview</h2>
      <p className="mt-1 text-slate-600">Daily snapshot of GyrosProject.</p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <p className="text-sm font-medium text-slate-500">{stat.label}</p>
            <p className="mt-2 text-3xl font-bold text-blue-900">{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-lg font-semibold text-blue-950">Recent Activity</h3>
        <ul className="mt-4 space-y-3 text-sm text-slate-700">
          <li>09:42 AM — Order #1042 paid</li>
          <li>09:15 AM — Prep list updated</li>
          <li>08:50 AM — New menu item added</li>
          <li>08:12 AM — Shift handoff note created</li>
        </ul>
      </div>
    </SidebarLayout>
  );
}
