# Nerja Food Guide

Gratis, statisk restaurangguide för Nerja, Spanien. Restauranger hämtas från OpenStreetMap via offentliga Overpass-servrar. Menylänkar är officiella OSM-länkar eller *overifierade kandidater* från restaurangernas webbplatser. Inga menyer kopieras eller lagras.

## Publicera
Under Settings → Pages, välj **Deploy from a branch**, **main**, **/(root)**. Kör sedan Actions → Daily restaurant update → Run workflow. GitHub Actions kör dagligen 05:17 UTC. Arbetsflödet behöver rättigheten Contents: read and write (Settings → Actions → General → Workflow permissions). Webbplatsen finns sedan på https://tuffysan.github.io/nerja-food-guide/.

## Begränsningar
Inte alla restauranger finns i OpenStreetMap. Inte alla restauranger publicerar menyer. Offentliga Overpass-servrar har användningsbegränsningar. Menylänkar kan vara inaktuella. Ingen garanti för fullständighet eller tillgänglighet. Inga betalda API:er krävs.
