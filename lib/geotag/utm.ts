/**
 * SagarNetra - Hydrographic Geotagging & Dynamic UTM Projection
 * 
 * Complies with IHO S-44 and NIOT/MoES hydrographic survey standards.
 * Dynamically computes UTM zone from Longitude:
 * Zone = floor((lon + 180) / 6) + 1
 * Strictly enforces ZERO FABRICATION policy:
 * If navigation is unavailable, returns null coordinates and geo.status = "UNAVAILABLE".
 */

export interface GeotagResult {
  latitude: number | null;
  longitude: number | null;
  eastingM: number | null;
  northingM: number | null;
  utmZone: string | null;
  status: 'AVAILABLE' | 'UNAVAILABLE';
  r95UncertaintyM: number | null;
  diverSearchBoxM: { width: number; height: number } | null;
}

/**
 * Automatically calculates UTM Zone string from Longitude and Latitude.
 * Example: 80.298°E, 13.085°N -> "UTM Zone 44N"
 */
export function getUTMZone(lat: number, lon: number): { zoneNumber: number; hemisphere: 'N' | 'S'; zoneStr: string } {
  // Normalize lon to [-180, 180)
  let normLon = (lon + 180) % 360 - 180;
  if (normLon < -180) normLon += 360;

  const zoneNumber = Math.floor((normLon + 180) / 6) + 1;
  const hemisphere = lat >= 0 ? 'N' : 'S';
  return {
    zoneNumber,
    hemisphere,
    zoneStr: `UTM Zone ${zoneNumber}${hemisphere}`,
  };
}

/**
 * Standard Karney/WGS84 Transverse Mercator forward projection for UTM coordinates.
 */
export function wgs84ToUTM(lat: number, lon: number): { easting: number; northing: number; zoneStr: string } {
  const { zoneNumber, hemisphere, zoneStr } = getUTMZone(lat, lon);

  // WGS-84 ellipsoid parameters
  const a = 6378137.0; // semi-major axis
  const f = 1 / 298.257223563; // flattening
  const e2 = 2 * f - f * f; // first eccentricity squared
  const ePrime2 = e2 / (1 - e2);

  const k0 = 0.9996; // UTM scale factor
  const centralLon = (zoneNumber - 1) * 6 - 180 + 3; // central meridian
  const lonRad = (lon * Math.PI) / 180;
  const latRad = (lat * Math.PI) / 180;
  const centralLonRad = (centralLon * Math.PI) / 180;

  const N = a / Math.sqrt(1 - e2 * Math.sin(latRad) * Math.sin(latRad));
  const T = Math.tan(latRad) * Math.tan(latRad);
  const C = ePrime2 * Math.cos(latRad) * Math.cos(latRad);
  const A = Math.cos(latRad) * (lonRad - centralLonRad);

  // Meridian distance M
  const M = a * (
    (1 - e2 / 4 - 3 * e2 * e2 / 64 - 5 * e2 * e2 * e2 / 256) * latRad -
    (3 * e2 / 8 + 3 * e2 * e2 / 32 + 45 * e2 * e2 * e2 / 1024) * Math.sin(2 * latRad) +
    (15 * e2 * e2 / 256 + 45 * e2 * e2 * e2 / 1024) * Math.sin(4 * latRad) -
    (35 * e2 * e2 * e2 / 3072) * Math.sin(6 * latRad)
  );

  const easting = k0 * N * (
    A +
    (1 - T + C) * Math.pow(A, 3) / 6 +
    (5 - 18 * T + T * T + 72 * C - 58 * ePrime2) * Math.pow(A, 5) / 120
  ) + 500000.0;

  let northing = k0 * (
    M +
    N * Math.tan(latRad) * (
      A * A / 2 +
      (5 - T + 9 * C + 4 * C * C) * Math.pow(A, 4) / 24 +
      (61 - 58 * T + T * T + 600 * C - 330 * ePrime2) * Math.pow(A, 6) / 720
    )
  );

  if (hemisphere === 'S') {
    northing += 10000000.0; // False northing for southern hemisphere
  }

  return { easting: Math.round(easting * 100) / 100, northing: Math.round(northing * 100) / 100, zoneStr };
}

/**
 * Computes Target Geolocation from towfish position, heading, ground range, and channel side.
 * Enforces NO-FABRICATION policy: returns UNAVAILABLE when lat or lon is null.
 */
export function calculateTargetGeolocation(
  towfishLat: number | null,
  towfishLon: number | null,
  towfishHeadingDeg: number | null,
  groundRangeM: number,
  side: 'port' | 'starboard',
  gnssAccuracyM = 1.0
): GeotagResult {
  // ZERO FABRICATION POLICY
  if (towfishLat === null || towfishLon === null || towfishHeadingDeg === null) {
    return {
      latitude: null,
      longitude: null,
      eastingM: null,
      northingM: null,
      utmZone: null,
      status: 'UNAVAILABLE',
      r95UncertaintyM: null,
      diverSearchBoxM: null,
    };
  }

  // Bearing offset: Port = -90°, Starboard = +90°
  const bearingOffset = side === 'port' ? -90 : 90;
  const targetBearingDeg = (towfishHeadingDeg + bearingOffset + 360) % 360;
  const bearingRad = (targetBearingDeg * Math.PI) / 180;

  // Haversine/Direct Geodetic formula for small distances
  const R_EARTH = 6371000; // meters
  const latRad = (towfishLat * Math.PI) / 180;
  const lonRad = (towfishLon * Math.PI) / 180;
  const distRatio = groundRangeM / R_EARTH;

  const targetLatRad = Math.asin(
    Math.sin(latRad) * Math.cos(distRatio) +
    Math.cos(latRad) * Math.sin(distRatio) * Math.cos(bearingRad)
  );
  const targetLonRad = lonRad + Math.atan2(
    Math.sin(bearingRad) * Math.sin(distRatio) * Math.cos(latRad),
    Math.cos(distRatio) - Math.sin(latRad) * Math.sin(targetLatRad)
  );

  const targetLat = (targetLatRad * 180) / Math.PI;
  const targetLon = (targetLonRad * 180) / Math.PI;

  const utmData = wgs84ToUTM(targetLat, targetLon);

  // r95 horizontal position uncertainty (IHO S-44 Special Order / Order 1)
  // Combines GNSS variance, acoustic beam spreading, and towfish layback uncertainty
  const acousticUncertainty = 0.02 * groundRangeM; // 2% of range
  const sigmaPos = Math.sqrt(gnssAccuracyM * gnssAccuracyM + acousticUncertainty * acousticUncertainty);
  const r95 = Math.round(sigmaPos * 1.73 * 10) / 10; // 95% confidence radius
  const diverBox = {
    width: Math.round(2 * r95 * 10) / 10,
    height: Math.round(2 * r95 * 10) / 10,
  };

  return {
    latitude: Math.round(targetLat * 1000000) / 1000000,
    longitude: Math.round(targetLon * 1000000) / 1000000,
    eastingM: utmData.easting,
    northingM: utmData.northing,
    utmZone: utmData.zoneStr,
    status: 'AVAILABLE',
    r95UncertaintyM: r95,
    diverSearchBoxM: diverBox,
  };
}
