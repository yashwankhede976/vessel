# Glossary

**Project:** Intelligent Freight Forecasting Model for Optimized Vessel Chartering and Bulk Cargo Procurement from Overseas to the East Coast of India
**Codename:** Vessel
**Document type:** Glossary of terms
**Status:** Draft v1.0

Terminology used across the specification. Definitions are written for a mixed audience (chartering, procurement, engineering) and reflect common industry usage.

---

## A

- **AIS (Automatic Identification System):** Shipborne transponder system broadcasting a vessel's identity, position, speed, and heading; the primary basis for vessel tracking and ETA inputs.
- **Alternative-port recommendation:** A suggestion to discharge at a different East Coast port when the primary port is congested, incompatible, or risk-exposed, shown with the landed-cost impact.
- **Arbitrage (origin arbitrage):** Exploiting cost differences between sourcing origins so that the origin with the lowest *total landed* cost is selected.

## B

- **Ballast:** A leg sailed without paying cargo (e.g. repositioning to load), during which the vessel may carry water ballast for stability. Ballast time is a cost/utilization concern.
- **Berth:** The specific location at a port where a vessel moors to load or discharge; each berth has physical constraints (draft, length).
- **Bulk cargo (dry bulk):** Unpackaged homogeneous cargo carried loose in the hold (e.g. coal, iron ore, grain). This project focuses on dry bulk, primarily coal.
- **Bunker / bunker price:** Marine fuel and its price; a major, volatile component of voyage cost and thus of freight and landed cost.

## C

- **Capesize:** A large dry-bulk vessel class (too big for the Panama/Suez in some configurations), typically for long-haul, high-volume cargoes.
- **Cargo intelligence / trade intelligence:** Insight into commodity trade flows (volumes, direction, demand/supply) that helps explain and anticipate freight movements.
- **Charter / chartering:** Hiring a vessel to carry cargo. The chartering desk decides which vessel, when, and under what contract structure.
- **Coal (thermal / coking):** The primary commodity in scope. Thermal (steam) coal is used for power generation; coking (metallurgical) coal is used in steelmaking.
- **Congestion (port congestion):** Vessels waiting for a berth beyond normal turnaround; increases waiting time, ETA uncertainty, and demurrage risk.
- **Contract type (spot / short-term / multi-voyage):** The structure of the freight commitment. *Spot* = a single voyage booked at current market rate; *short-term* = a limited-period commitment; *multi-voyage* = several shipments under one arrangement, often to reduce cost and rate risk.

## D

- **Demurrage:** A penalty the charterer pays the shipowner when loading/discharging exceeds the agreed laytime; a major avoidable cost driven by congestion and poor laycan planning.
- **Despatch:** The opposite of demurrage — a payment/credit when operations finish faster than the agreed laytime.
- **Draft (draught):** The vertical distance from the waterline to the bottom of the hull; a loaded vessel's draft must not exceed a port/berth's maximum draft (a key constraint at draft-limited East Coast ports).
- **DWT (deadweight tonnage):** The total weight a vessel can carry (cargo, fuel, stores, etc.); a core capacity/compatibility attribute.

## E

- **East Coast India ports (in scope):** Paradip, Visakhapatnam, Gangavaram, Gopalpur, Dhamra, Sagar/Sandheads, Haldia.
- **ETA (Estimated Time of Arrival):** Predicted arrival time at the destination port, accounting for transit, weather, and expected port waiting.
- **Explainable AI (XAI):** Methods and UI that expose *why* a recommendation was made — its drivers, confidence, and assumptions — so users can trust and challenge it.

## F

- **FOB (Free On Board):** A trade term where the buyer takes responsibility (and arranges freight) once cargo is loaded at the origin port; relevant to who charters and to landed-cost buildup.
- **Freight rate:** The price to move cargo on a lane, commonly expressed per tonne or per voyage; the central quantity the platform forecasts.
- **Forecast horizon:** The time span a forecast covers — *short-term* (days–weeks) or *medium-term* (weeks–months) in this project.

## G

- **Gangavaram:** A deep-draft East Coast India port in scope.
- **Geopolitical / disruption risk:** Risk from sanctions, conflict, canal/strait closures, or other events that disrupt lanes, origins, or costs.
- **Gopalpur:** An East Coast India port in scope.

## H

- **Haldia:** A draft-constrained East Coast India port (Hooghly river system) in scope; approaches include Sandheads.

## L

- **Laycan (laydays/cancelling):** The agreed window during which a vessel must arrive and be ready to load; arriving outside it risks cancellation or demurrage. *Laycan optimization* chooses windows that minimize demurrage risk while staying feasible.
- **Laytime:** The time allowed (by contract) for loading/discharging before demurrage applies.
- **Landed cost (total landed cost):** The all-in delivered cost per tonne: cargo cost + freight + bunker-adjusted voyage cost + port/handling + expected demurrage + applicable duties/other.
- **Lane:** An origin→destination trade route (e.g. Australia→Paradip). Forecasts and analytics are organized by lane.
- **LOA (Length Overall):** A vessel's maximum length; a berth-compatibility constraint.

## M

- **MAPE (Mean Absolute Percentage Error):** A common forecast-accuracy metric; lower is better.
- **Market-entry timing:** Guidance on whether to book now or wait, derived from the freight forecast trajectory.
- **Monsoon / cyclone risk:** Seasonal weather risk (notably in the Bay of Bengal) affecting transit, port operations, ETA, and demurrage on East Coast lanes.
- **Multi-origin procurement optimization:** Selecting the origin (or mix of origins) that delivers required tonnage at least total landed cost and acceptable risk.
- **Multi-voyage:** See *Contract type*.

## O

- **Open (vessel open / open date):** The date/place a vessel becomes available for its next employment; central to availability intelligence and idle-vessel recommendations.

## P

- **Panamax / Supramax / Capesize:** Common dry-bulk vessel size classes, differing in DWT and dimensions, which affect port compatibility and rates.
- **Paradip:** A major East Coast India coal-handling port in scope.
- **Port & berth constraints:** The physical/operational limits of a port or berth (max draft, LOA, beam, DWT, cargo-handling capability) that determine feasibility.

## S

- **Sagar / Sandheads:** A pilot station / anchorage area at the approaches to the Hooghly (serving Haldia); in scope as a location for approach and lightening operations.
- **Spot (spot market):** Booking a single voyage at the prevailing market rate; the reactive default the platform aims to reduce reliance on.
- **Supramax:** A mid-size dry-bulk vessel class.

## T

- **Total landed cost:** See *Landed cost*.
- **Trade flow:** The movement of a commodity between regions over time; a driver of demand and freight.

## V

- **Vessel availability intelligence:** Identifying suitable open/available tonnage for a required cargo, origin, and timeframe.
- **Vessel-port compatibility:** Whether a specific vessel physically/operationally fits a target port/berth given draft, LOA, beam, and DWT.
- **Vessel tracking:** Monitoring vessel position and voyage status (typically via AIS).
- **Visakhapatnam (Vizag):** A major East Coast India port in scope.
- **Voyage economics:** The cost/revenue analysis of a voyage (freight earned vs bunker, port, canal, and time costs); underpins idle-vessel employment and contract decisions.

## W

- **What-if simulation:** Adjusting key variables (bunker price, congestion, demand, timing) to see the effect on landed cost, risk, and recommendations versus a base case.
- **Weather & marine risk:** Risk to voyages and port operations from weather/sea state, notably monsoon and cyclones in the Bay of Bengal.

## Reference note

**Kpler** is cited in this project only as a *high-level capability and user-experience reference* for maritime/commodity intelligence platforms. Vessel does not use Kpler's proprietary data, branding, UI, content, or implementation.

## Related documents

- [PROJECT_SPECIFICATION.md](./PROJECT_SPECIFICATION.md)
- [BUSINESS_REQUIREMENTS.md](./BUSINESS_REQUIREMENTS.md)
- [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md)
- [NON_FUNCTIONAL_REQUIREMENTS.md](./NON_FUNCTIONAL_REQUIREMENTS.md)
