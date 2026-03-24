# Load-pull embedding for two tuners

Dette oppsettet gjør to ting:

1. Regner fra ønsket impedans ved DUT-plan tilbake til nødvendig tunerrefleksjon.
2. Regner fra en valgt tunerstate fram til faktisk impedans ved DUT-plan.

Det støtter begge metodene:

- `port_extension`: enkel modell med elektrisk delay og valgfritt tap.
- `s2p`: full 2-portmodell fram til DUT-plan.

## Filer

- `load_pull_embedding.py` – Python-modul.
- `calibration_format_example.json` – eksempel på tunerkalibreringsformat.
- `example_system_config.json` – eksempel på systemkonfigurasjon for source og load.
- `example_interface.s2p` – liten eksempel-S2P.
- `example_usage.py` – demonstrasjon.

## Viktige konvensjoner

### 1. Tunerkalibrering

Kalibreringen ligger per state:

- `x`
- `y`
- en liste med frekvenspunkter
- refleksjon `gamma` i tunerplanet

Eksempel:

```json
{
  "z0": 50.0,
  "states": [
    {
      "x": 12000,
      "y": 850,
      "points": [
        {"freq_mhz": 433, "gamma_ri": [0.51, -0.18]}
      ]
    }
  ]
}
```

### 2. Port extension

Dette brukes når mellomstykket mellom tuner og DUT i praksis er en linje.

```json
{
  "type": "port_extension",
  "electrical_delay_ps": 82.0,
  "one_way_loss_db": 0.08
}
```

- `electrical_delay_ps` er **énveis** delay.
- refleksjonsrotasjonen blir da automatisk dobbelt vei.
- `one_way_loss_db` er valgfritt og brukes også som énveisverdi.

### 3. S2P embedding

Dette brukes når du vil ha med launch, PCB, fixture, biasnett osv.

```json
{
  "type": "s2p",
  "files": ["example_interface.s2p"]
}
```

Hvis du vil kaskadere flere blokker, bruk:

```json
{
  "type": "cascade_s2p",
  "files": ["pcb.s2p", "biastee.s2p", "fixture.s2p"]
}
```

**Portkonvensjon:**

- Port 1 = DUT-plan
- Port 2 = tunerplan

Det må være slik i alle S2P-filer du bruker.

## Matematikken som brukes

### Port extension

Fra tuner til DUT:

- `Γ_DUT = Γ_tuner * round_trip_factor`

Der round-trip-faktoren består av:

- fase fra elektrisk delay
- amplitude fra toveis tap

Fra DUT til tuner:

- `Γ_tuner = Γ_DUT / round_trip_factor`

### S2P

Fra tuner til DUT:

- `Γ_DUT = S11 + (S12*S21*Γ_tuner)/(1 - S22*Γ_tuner)`

Fra DUT til tuner:

- `Γ_tuner = (Γ_DUT - S11) / (S12*S21 + S22*(Γ_DUT - S11))`

## API du bruker

### Laste systemet

```python
from pathlib import Path
from load_pull_embedding import LoadPullSystem

system = LoadPullSystem.from_json(Path("example_system_config.json"))
```

### Finne tunerstate for ønsket DUT-impedans

```python
result = system.side("load").solve_for_z_dut(433e6, complex(12.0, 18.0))
print(result.as_dict())
```

### Finne faktisk DUT-impedans fra kjent tunerstate

```python
from load_pull_embedding import TunerState

info = system.side("load").dut_impedance_from_state(433e6, TunerState(x=12000, y=850))
print(info)
```

## Det du må fylle inn i dine egne filer

### Kalibrering

Bytt ut `calibration_format_example.json` med den virkelige tunerkalibreringen din.

Hver state må ha:

- `x`
- `y`
- `gamma` i tunerplanet
- ett eller flere frekvenspunkter

### Source-side og load-side

Du kan ha ulik metode på hver side. Eksempel:

- `source` bruker port extension
- `load` bruker S2P

eller begge kan bruke S2P.

### S2P-filer

Mål S2P helt fram til DUT-plan, og pass på at:

- port 1 er DUT-plan
- port 2 er tunerplan
- referanseimpedansen er korrekt
- frekvensområdet dekker målepunktene dine

## Anbefalt praktisk bruk

### Første nivå

Bruk `port_extension` hvis du vil komme raskt i gang og mellomstykket er nesten bare linje.

### Endelig bruk

Bruk `s2p` når målet er å vite sikkert hva halvlederen faktisk ser.

## Begrensninger i denne modulen

Denne modulen er bevisst enkel og rett fram:

- 2-port Touchstone (`.s2p`) only
- lineær interpolasjon i frekvens
- S2P-kaskadering krever samme frekvensgrid i alle filene
- nærmeste state velges etter minste `|Γ_cal - Γ_req|`

Hvis du senere vil, er naturlige neste steg:

- støtte for tettere søk/interpolasjon mellom states
- dekning-/maskeringskart i DUT-plan
- logging rett til målefilene dine
- integrasjon direkte mot tuner-kommandoene dine
