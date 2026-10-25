
export default function ApiStatus({ status }) {
  const label = { checking: "Checking API", connected: "API online", offline: "API offline" };
  return <div className={"api-status api-status--" + status} role="status" aria-live="polite"><span className="status-dot" />{label[status]}</div>;
}
