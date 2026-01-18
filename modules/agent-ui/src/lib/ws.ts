import type { StoredSettings } from "./storage";

export function getWsUrl(settings: StoredSettings, path: string) {
  const base = settings.serverUrl.replace(/\/$/, "");
  const wsBase = base.replace(/^http/, "ws");
  return `${wsBase}${path}`;
}
