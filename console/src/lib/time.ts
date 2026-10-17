// Unit conversion and formatting only (MJD -> wall-clock labels). No astronomy here.
const MJD_UNIX_EPOCH = 40587;

// Rounded to the nearest second so 21:59:59.999 (float MJD) never prints as the wrong minute or hour.
export const mjdToDate = (mjd: number): Date => new Date(Math.round((mjd - MJD_UNIX_EPOCH) * 86400) * 1000);

export function fmtTime(mjd: number, timeZone = "UTC"): string {
  return mjdToDate(Math.round(mjd * 1440) / 1440).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone, hour12: false });
}

export function fmtDate(mjd: number, timeZone = "UTC"): string {
  return mjdToDate(mjd).toLocaleDateString("en-CA", { timeZone });
}

export function fmtDateTime(mjd: number, timeZone = "UTC"): string {
  return `${fmtDate(mjd, timeZone)} ${fmtTime(mjd, timeZone)}`;
}

export function tzAbbrev(mjd: number, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone, timeZoneName: "short" }).formatToParts(mjdToDate(mjd));
  return parts.find((p) => p.type === "timeZoneName")?.value ?? timeZone;
}
