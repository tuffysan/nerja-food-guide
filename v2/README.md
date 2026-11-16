# Nerja Food Guide — clean rebuild (V2)

This is a **new implementation**, isolated from the currently published app.
Do not publish V2 over main until acceptance checks pass.

## Product contract

- Every restaurant can appear in the directory without a menu.
- A menu is counted only when a restaurant-specific menu page, PDF, image or actual dish list is evidenced. A homepage is **not** a menu.
- No requirement that dishes have prices.
- Links retain provenance, discovery date and validation state.
- Never erase existing confirmed content on a transient network error.
- Photos require explicit restaurant association and permission/license; otherwise show a neutral placeholder.
- Free sources and open-source tools only; respect robots.txt and rate limits.
- Display **verified**, **candidate** and **unavailable** separately. Never report candidates as verified menus.

## Data model

Restaurant: id, name, coordinates, address, category, website, source.
Menu evidence: restaurant_id, url, format, source, discovered_at, checked_at, status, reason, dishes.
Photo: restaurant_id, url, source_url, license, attribution, checked_at.

## Build pipeline

1. Ingest OSM directory + curated official restaurant sources.
2. Normalize IDs and deduplicate by stable ID, name and coordinates.
3. Crawl restaurant-specific official websites within bounded limits.
4. Discover menu links in HTML, sitemap, PDF and QR codes.
5. Validate candidate URLs and whether they are *actually* menus.
6. Extract dish names from HTML/PDF/OCR where reliable; prices optional.
7. Collect explicitly attributed, freely licensed photos.
8. Merge without deleting last-known-good evidence on temporary failures.
9. Validate schema, security, links and regression metrics.
10. Publish a human-readable report with verified restaurants, menus, photos, new discoveries and failures.
11. Publish site only when all release checks pass.

## Release gates

- No JavaScript/Python syntax errors.
- No invalid JSON or mismatched restaurant IDs.
- No generic homepage reported as a verified menu.
- No decrease in verified menu/photo coverage without an explicit reviewed removal.
- No unlicensed or mismatched restaurant photos.
- Reported counts must match visible site filters.
- Run mobile browser smoke tests before switching production.

## Rollout

Build V2 in this branch and preview it separately. Keep the current production site intact until V2 passes real-data and browser acceptance checks. Only then replace the old app.
