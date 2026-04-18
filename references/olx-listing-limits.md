# OLX listing limits — skill-facing cheat sheet

Source: OLX Regulamin, **Załącznik nr 3 — Limity Ogłoszeń**, obowiązuje
od 29 września 2025 r. Full PDF:
<https://pomoc.olx.pl/olxplhelp/s/article/za%C5%82%C4%85cznik-nr-3-limity-og%C5%82osze%C5%84-V41-olx>.
Re-check the source if a publish is rejected with a limit error —
OLX revises these numbers every few months.

## The rule in one paragraph

A limit is the max number of **active** listings you can hold in a
category (or group of categories) at any time. It **renews 30 days
after the most recent listing you published within that limit**
(rolling window, not calendar month — a few categories use 90/180/360/
730 days, flagged below). Hit the limit → OLX refuses the next publish
for that category until the window rolls forward; there is no
"pay-per-extra-listing" escape hatch for private users (you'd have to
wait, delete an old one, or accept that the category is just
rate-limited for you).

**Private vs. business.** Every category has two limits: one for
**users prywatnych** (us — `private_business: "private"` in the create
payload) and one for **Użytkownicy Biznesowi i profesjonalni**. The
business limits are tighter or zero across the board; they only kick
in if OLX has flagged the account as biznesowy. This skill always
posts with `private_business: "private"` so only the left column
applies. Do **not** worry about the business numbers.

## What matters for `olx new` / `olx manage`

### Hard blockers — these categories have **no free listings** for privates

Treat these as "paid-only, don't try to post for free":

- **Motoryzacja** — Samochody osobowe, Motocykle i Skutery,
  Dostawcze i Ciężarowe, Budowlane, Przyczepy i Naczepy, Samochody na
  części (limit 0). Also `Motoryzacja / Pozostała motoryzacja` = 0.
  (But `Motoryzacja / Części samochodowe`, `Części motocyklowe`,
  `Opony i Felgi`, `Sprzęt car audio`, `Wyposażenie i akcesoria` all
  get **1** per 30d.)
- **Nieruchomości — sale/rent of apartments, houses, land, offices,
  halls, garages** (limit 0). Carve-outs:
  - `Mieszkania/Domy/Garaże > Wynajem` = 1 per **360 days**
  - `Stancje i pokoje` = 1 per **180 days**
  - `Za granicą` = 2 per **730 days**
- **Praca, Usługi, Wypożyczalnia** — fully paid.
- **Noclegi** — paid except `Noclegi/Dla Ukrainy` and `Noclegi/Za
  granicą` subcats.
- **Zwierzęta / Psy rasowe, Koty rasowe** — paid.
- **Rolnictwo / Ciągniki, Maszyny rolnicze, Przyczepy** — paid.

If the drafted category falls into one of these, the skill must warn
the user before attempting publish — a `create_advert` call will come
back with an error, not just a silent drop.

### Soft limits — watch the count

Grouped by what a private seller actually lists. Numbers are max
active listings per 30-day rolling window (unless a different period
is specified).

**Clothes & kids — generous:**
- `Moda` — **no limit** for private.
- `Dla Dzieci` — **no limit** overall, BUT:
  - `Dla Dzieci / Wózki dziecięce` = 10
  - `Dla Dzieci / Foteliki - Nosidełka` = 10

**Sport & hobby — this is the one the skill will brush against a lot:**
- `Sport i Hobby / Rowery / Akcesoria rowerowe + Części rowerowe +
  Odzież i obuwie rowerowe` — **4 combined** (shared bucket across
  all three). Bike lights, helmets, inner tubes, jerseys all count
  together.
- `Sport i Hobby / Rowery / <actual bikes>` — **2 combined** across
  BMX, Rowery górskie/szosowe/miejskie/trekkingowe/gravel/składane/
  crossowe/dziecięce/elektryczne/Pozostałe/Przyczepki rowerowe.
- `Sport i Hobby / Sporty zimowe` — 5 (ski helmets, boots, skis).
- `Sport i Hobby / Fitness` — 5.
- `Sport i Hobby / Turystyka` — 5.
- `Sport i Hobby / Wędkarstwo` — 5.
- `Sport i Hobby / Gry planszowe` — 5.
- `Sport i Hobby / Skating` — 5.
- `Sport i Hobby / Akcesoria jeździeckie` — 5.
- `Sport i Hobby / Pozostały sport i hobby` — 5.
- `Sport i Hobby / Bilety` — 10.
- `Sport i Hobby / Militaria` — 10.
- `Sport i Hobby / Społeczność` — 10.
- `Sport i Hobby / Sporty drużynowe` — 50.
- `Sport i Hobby / Sporty towarzyskie` — 20.
- `Sport i Hobby / Sporty wodne / *` — mostly **1** per subcategory
  (Łodzie/Silniki/Skutery/Kajaki/Kitesurfing/Windsurfing/SUP/
  Pływanie/Pozostałe), with Akcesoria i części=2, Osprzęt żeglarski=2,
  Sprzęt ratunkowy=2.
- `Sport i Hobby / Pojazdy elektryczne` — 2.

**Electronics — mostly 2, hits the limit fast:**
- `Elektronika / Komputery / *` — 2 per subcat, except
  `Akcesoria komputerowe` = 5.
- `Elektronika / Fotografia / *` — 2 per subcat, except
  `Akcesoria fotograficzne` = 5.
- `Elektronika / Sprzęt audio / *` — 2 per subcat, except
  `Akcesoria` and `Części` = 5.
- `Elektronika / Sprzęt video / *` — 2, except `Akcesoria i części` = 10.
- `Elektronika / Sprzęt AGD / *` — 2, except `Części i akcesoria` = 5.
- `Elektronika / TV / Telewizory + Pozostałe` — 2; `TV / Akcesoria` = 10,
  `TV / Części` = 10.
- `Elektronika / Telefony / Smartfony + Stacjonarne + Złote numery` — 2;
  `Telefony / Akcesoria` = 10.
- `Elektronika / Smartwatche i opaski / *` — 2, akcesoria = 5.
- `Elektronika / Gry i Konsole / Konsole + Pozostałe` — 2;
  `Akcesoria gamingowe` = 10, `Kolekcje graczy` = 10;
  `Gry` — no limit.
- `Elektronika / Pozostała elektronika` — 2.

**Dom i Ogród — mostly 2:**
- `Dom i Ogród / Budowa / *` — 2 per subcat, `Okna` = 2 per 90 days.
- `Dom i Ogród / Instalacje / *` — 1–2 (Fotowoltaika, Klimatyzacja,
  Pozostałe = 1; Elektryka, Hydraulika = 2).
- `Dom i Ogród / Wykończenie wnętrz / *` — 2 all subcats.
- `Dom i Ogród / Meble / *` — **2** across the board, with 90-day
  window on `Biurka`, `Sofy i kanapy`, so two sofas = 90 days of
  cooldown. `Meble dla dzieci` = 5.
- `Dom i Ogród / Narzędzia / *` — mostly 2; power tools (Agregaty,
  Betoniarki, Myjki, Pistolety, Pompy, Sprężarki) = 1;
  `Narzędzia ręczne` = 2 per 90 days; `Części do narzędzi` and
  `Osprzęt` = 3.
- `Dom i Ogród / Ogród / *` — 2; `Kosiarki` = 2 per 90 days.
- `Dom i Ogród / Ogrzewanie / *` — 1–3 (Kotły, Pompy ciepła,
  Podgrzewacze = 1; Akcesoria, Części, Żarówki = 3).
- `Dom i Ogród / Oświetlenie / *` — 2 (Akcesoria, Żarówki = 3).
- `Dom i Ogród / Wyposażenie wnętrz / *` — mostly 2;
  `Dekoracje` = 5 (was 10, dropped in V41); `Rośliny doniczkowe` = 5;
  `Zastawa stołowa` = 5; textiles (Pościel, Obrusy, Ręczniki,
  Przybory kuchenne, Świece, Wystrój okien) = 3.
- `Dom i Ogród / Supermarket` — 10.
- `Dom i Ogród / Pozostałe dom i ogród` — 2.

**Zdrowie i Uroda:**
- `Makijaż`, `Perfumy` — 50.
- `Pielęgnacja ciała/twarzy`, `Paznokcie`, `Włosy`, `Produkty CBD`,
  `Witaminy i suplementy` — 10.
- `Zdrowie / *` (większość) — 3.

**Zwierzęta:**
- `Akcesoria dla zwierząt`, `Karma i przysmaki` — 50.
- `Akwarystyka`, `Gryzonie i Króliki`, `Pozostałe`, `Terrarystyka`,
  `Ptaki` — 5–20.
- `Konie` — 1 per 90 days.
- (Psy rasowe / Koty rasowe — paid, see "Hard blockers".)

**Muzyka i Edukacja:**
- `Muzyka i Edukacja` (top-level mixed) — 100.
- `Instrumenty` — 10.
- `Książki` — no limit for private.

**Antyki i Kolekcje:**
- Most subcats 20–30.
- `Stare instrumenty`, `Stare meble` — 5.
- `Stare rowery` — 2.
- Rękodzieło — 30 per subcat.

**Firma i Przemysł (even for private sellers this shows up):**
- Mostly 1 per subcat. `Części do maszyn i urządzeń` = 3.
  `Wyposażenie warsztatów` = 5. `Kontenery`, `Maszyny i urządzenia`,
  `Sprzedam firmę`, `Gastronomia / Przyczepy gastronomiczne` = 0
  (fully paid).

## What the skill should do with this

Minimum (current v1):

1. **Drafting step:** after the category is proposed, surface the
   applicable limit to the user alongside the rest of the draft.
   Example line in the proposal: `Kategoria: Sport i Hobby / Rowery
   / Akcesoria rowerowe   (limit 4 na 30 dni, łączony z Części
   rowerowe i Odzież i obuwie rowerowe)`.

2. **Hard-blocker guard:** if the proposed category is in the
   "limit 0 / paid-only" list (Motoryzacja sprzedaż, Nieruchomości
   sprzedaż, Praca, Usługi, Wypożyczalnia, Psy/Koty rasowe, etc.),
   refuse to attempt a free publish and tell the user this category
   requires a paid post.

Nice-to-have (v2):

3. **Live pre-check via `Ads` GraphQL.** Before publishing, call
   `myAds.ads(filters:{status:ACTIVE})`, count how many active
   listings the user already has in the proposed category (or in the
   grouped bucket — the Rowery accessories group is shared across
   three category IDs; keep a local map of group membership). If
   post would exceed the limit, warn: "this would be your 5th active
   listing in [bucket] against a limit of 4; publishing will be
   refused."

4. **Shared buckets map.** Encode the two known shared buckets:
   - Rowery accessories bucket = {`Akcesoria rowerowe`,
     `Części rowerowe`, `Odzież i obuwie rowerowe`} → limit 4.
   - Rowery bikes bucket = {BMX, Rowery crossowe, Rowery dziecięce,
     Rowery elektryczne, Rowery miejskie, Rowery szosowe, Rowery
     trekkingowe, Rowery gravel, Rowery składane, Rowery górskie,
     Pozostałe rowery, Przyczepki rowerowe} → limit 2.
   - Motoryzacja parts bucket = {Części samochodowe, Części
     motocyklowe, Opony i Felgi, Sprzęt car audio, Wyposażenie i
     akcesoria} → limit 1.

5. **Window awareness.** For 90/180/360/730-day categories, if the
   user has ever posted there before, warn them of the long
   cooldown before they commit to a draft.

## Categories encoded as data

The create payload takes an integer `category_id`, not a path. To
apply these limits programmatically, we'd need a `category_id →
{limit, window_days, bucket}` map. That map doesn't exist yet; first
time a limit question comes up in practice, build it alongside the
live pre-check (v2 point 3). For v1, the skill surfaces the text
description to the user and relies on the user's eyeball + the live
OLX error response as the final gate.
