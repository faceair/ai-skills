import { datafluxRum } from "@cloudcare/browser-rum";

export function startRum(): void {
  datafluxRum.init(window.__RUM_CONFIG__);
}
