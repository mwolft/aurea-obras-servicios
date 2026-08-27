export const siteUrl = "https://www.aureaobrasyservicios.com";

export function getPublicUrl(path = "/"): string {
  return new URL(path, siteUrl).toString();
}
