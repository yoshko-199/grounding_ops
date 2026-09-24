# How to try the demo pack

For when you want to watch the ten supplied claims land on the full range of
verification levels, from *Accurate* to *Insufficient Data*. Against the real
packs every one of them is *Insufficient Data*, because nothing covers them.

The demo pack, `packs/demo/xd.toml`, is a synthetic jurisdiction, `XD`. Its
custodians are fake, and each is named "XD Demo …". Its values, in
`engine/custodians/demo.py`, **are invented**. Each was chosen to land one
claim on one level, and none may be quoted as a real figure. The real-figures
counterpart is [a scaffold](../spec/packs/demo-real.md) whose figures stay
blank until they are fetched from each authority's own publication.

## Run a claim

```
PYTHONPATH=. python3 cli/verify.py "the homicide rate fell since 1991" \
  --packs packs/demo --jurisdiction XD --store :memory:
```

`--jurisdiction XD` is needed. The pack deliberately declares no real
country's name, so a claim that says "U.S." doesn't resolve to it by itself.
A synthetic pack that claimed a real jurisdiction's name would let invented
values answer a real question.

## In the web UI

```
PYTHONPATH=. python3 cli/serve.py --packs packs/demo --store /tmp/grounding-demo.db
```

Open `http://127.0.0.1:8000/`, choose **XD** as the jurisdiction, and submit
a claim from the table below.

## What each claim shows

The variants (`1v`, `8v`, `8x` and `10v`) are edited versions of the
supplied claims, added to reach levels the originals can't. They are not the
claimant's words.

| # | Claim | Verdict | Why |
|---|---|---|---|
| 1 | Water boils at 100 degrees Celsius (212 degrees Fahrenheit) at sea level. | Substantially inaccurate | "100" verifies against the Celsius series. "212" is compared against the same Celsius series and contradicted, because the engine doesn't read units ([R1](../spec/proposals/v0.6-requirements.md#r1-units)) |
| 1v | Water boils at 100 degrees Celsius at sea level. | Indeterminate | Verified, but a level claim asserts no direction for the robustness sweep to test, so the verdict is capped ([R6](../spec/proposals/v0.6-requirements.md#r6-level-claims-and-accurate)) |
| 2 | Pizza is the most delicious food in the world. | Insufficient Data | Opinion: out of scope whatever sources exist |
| 3 | Humans are classified as mammals. | Insufficient Data | A classification with no quantity: out of scope ([R5](../spec/proposals/v0.6-requirements.md#r5-classification-facts)) |
| 4 | King John of England signed the Magna Carta in 1225 | Insufficient Data | The measure binds, but its custodian, the XD Demo Archive, has no adapter, so "in 1225" is *unreachable*, not *unverified*. A year is a time period, so it could not be contradicted anyway ([R2](../spec/proposals/v0.6-requirements.md#r2-event-dates)) |
| 5 | Covid-19 epidemic originated from a Chinese research lab | Insufficient Data | Causal, with no quantity: out of scope |
| 6 | Vaccines cause Autism in children | Insufficient Data | Causal: out of scope, and no derived element, because "cause" is active voice ([R3](../spec/proposals/v0.6-requirements.md#r3-active-voice-causal-verbs)) |
| 7 | If you put two sheep in a field… | Insufficient Data | Arithmetic: out of scope |
| 8 | the density of steel is 7700 kg per cubic metre. | Insufficient Data | "Steel" matches two measures from two custodians (carbon and stainless) equally, and binding reports them as contested. v0.5 says both figures should be reported and the claim be *Indeterminate*; today it folds to Insufficient Data ([D1](../spec/proposals/v0.6-requirements.md#d1-contested-by-definition-folds-into-insufficient-data)) |
| 8v | the density of carbon steel is 7700 kg per cubic metre. | Indeterminate | Verified within band B (the published value is close but not equal), and capped as a level claim. The `rounded` tag is recorded but not yet shown ([D2](../spec/proposals/v0.6-requirements.md#d2-the-band-b-rounded-tag-is-never-shown)) |
| 8x | the density of carbon steel is 9000 kg per cubic metre. | False | Band C: contradicted |
| 9 | The U.S. has a highly progressive tax-and-transfer system… | Insufficient Data | Evaluative, with no quantity: out of scope |
| 10 | In the U.S … the nation's murder rate has been cut by more than half since 1991 | Misleading | The fall verifies against the series start, but the latest year rose, so the claim flips against the prior-year baseline. The sweep is catching a baseline choice |
| 10v | the homicide rate fell since 1991 | Accurate | Every element verifies, and the conclusion holds under every declared baseline |

`tests/unit/test_demo_pack.py` pins every row, so changing a demo value moves
the claim it serves and fails a test.

## Where the demo stops

The demo shows what the engine does today, including where it falls short.
The gaps it exposed, and three places where today's behaviour diverges from
the specification, are written up as
[requirements for the next specification version](../spec/proposals/v0.6-requirements.md).
