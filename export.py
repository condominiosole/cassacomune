#!/usr/bin/env python3
"""
Cassa Comune - esportatore ODS -> JSON

Legge un file LibreOffice Calc .ods senza richiedere LibreOffice installato
e genera web/dati.json per la dashboard GitHub Pages.

Struttura prevista dal file Cassa Comune:
- Movimenti
  Data | Descrizione | Categoria | Importo (€) | Pagato da |
  Partecipanti (nomi separati da ;) | N. partecipanti | Quota (€) | Note
- Versamenti
  Data | Partecipante | Importo (€) | Note
- Partecipanti
  Nome | Totale versato | Quota consumata | Saldo

I saldi vengono ricalcolati dai dati grezzi di Movimenti e Versamenti,
quindi non dipendono da formule eventualmente non aggiornate nel foglio.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET


NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def cell_text(cell: ET.Element) -> str:
    # Il testo di Calc può essere distribuito in più text:p.
    parts = []
    for elem in cell.iter():
        if local_name(elem.tag) == "p":
            txt = "".join(elem.itertext()).strip()
            if txt:
                parts.append(txt)
    if parts:
        return " ".join(parts).strip()

    # Fallback per celle semplici.
    return " ".join("".join(cell.itertext()).split()).strip()


def read_ods(path: Path) -> dict[str, list[list[str]]]:
    if not path.exists():
        raise FileNotFoundError(f"File ODS non trovato: {path}")

    with zipfile.ZipFile(path, "r") as z:
        if "content.xml" not in z.namelist():
            raise ValueError("Il file ODS non contiene content.xml")
        root = ET.fromstring(z.read("content.xml"))

    sheets = {}

    for table in root.findall(".//table:table", NS):
        name = table.attrib.get(f"{{{NS['table']}}}name", "")
        rows = []

        for row in table.findall("table:table-row", NS):
            values = []

            for cell in row.findall("table:table-cell", NS):
                repeated = int(
                    cell.attrib.get(
                        f"{{{NS['table']}}}number-columns-repeated", "1"
                    )
                )
                value = cell_text(cell)
                values.extend([value] * repeated)

            # Elimina solo le colonne vuote finali.
            while values and values[-1] == "":
                values.pop()

            if values:
                rows.append(values)

        sheets[name] = rows

    return sheets


def rows_to_dicts(rows: list[list[str]]) -> list[dict[str, str]]:
    if not rows:
        return []

    headers = rows[0]
    result = []

    for row in rows[1:]:
        if not any(str(x).strip() for x in row):
            continue

        item = {}
        for i, header in enumerate(headers):
            if not header:
                continue
            item[header.strip()] = row[i].strip() if i < len(row) else ""
        result.append(item)

    return result


def parse_money(value: str) -> float:
    if value is None:
        return 0.0

    s = str(value).strip()
    if not s:
        return 0.0

    # Gestisce 1.234,56 e 1234.56.
    s = s.replace("€", "").replace(" ", "")

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")

    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_int(value: str) -> int:
    try:
        return int(float(parse_money(value)))
    except (ValueError, TypeError):
        return 0


def round_money(value: float) -> float:
    # Evita -0.0 e residui floating point.
    rounded = round(float(value) + 0.0, 2)
    return 0.0 if abs(rounded) < 0.005 else rounded


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip())


def parse_participants(value: str) -> list[str]:
    if not value:
        return []

    # Il file usa ; come separatore.
    names = [normalize_name(x) for x in value.split(";")]
    return [x for x in names if x]


def normalize_date(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""

    # Nel file attuale le date sono dd/mm/yy, es. 29/06/26.
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Se non riconosciuta, la lasciamo invariata.
    return value


def date_sort_key(value: str) -> tuple[int, str]:
    normalized = normalize_date(value)
    return (1 if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized) else 0, normalized)


def require_sheet(sheets: dict, name: str) -> list[dict[str, str]]:
    if name not in sheets:
        raise ValueError(
            f"Foglio '{name}' non trovato. Fogli disponibili: "
            + ", ".join(sheets.keys())
        )
    return rows_to_dicts(sheets[name])


def export_ods(ods_path: Path, json_path: Path) -> dict:
    sheets = read_ods(ods_path)

    movimenti = require_sheet(sheets, "Movimenti")
    versamenti = require_sheet(sheets, "Versamenti")

    # Partecipanti: usiamo l'ordine del foglio Partecipanti quando presente.
    participant_order = []
    if "Partecipanti" in sheets:
        participant_rows = rows_to_dicts(sheets["Partecipanti"])
        for row in participant_rows:
            name = normalize_name(row.get("Nome", ""))
            if name and name not in participant_order:
                participant_order.append(name)

    # Aggiunge eventuali nomi presenti nei versamenti o nelle spese.
    for row in versamenti:
        name = normalize_name(row.get("Partecipante", ""))
        if name and name not in participant_order:
            participant_order.append(name)

    movement_records = []
    consumed = {name: 0.0 for name in participant_order}

    total_spese = 0.0

    for row in movimenti:
        amount = parse_money(row.get("Importo (€)", ""))
        if amount == 0 and not row.get("Descrizione", "").strip():
            continue

        names = parse_participants(
            row.get("Partecipanti (nomi separati da ;)", "")
        )

        # Se la colonna dei partecipanti è vuota, prova a usare il pagato da
        # come fallback, senza inventare altri partecipanti.
        payer = normalize_name(row.get("Pagato da", ""))
        for name in names:
            if name not in participant_order:
                participant_order.append(name)
                consumed[name] = 0.0

        count = len(names)

        # Quota per partecipante. Se il numero dichiarato è disponibile ma
        # la lista è incompleta, la lista reale ha comunque precedenza.
        quota = amount / count if count else 0.0

        for name in names:
            consumed[name] = consumed.get(name, 0.0) + quota

        total_spese += amount

        movement_records.append(
            {
                "data": normalize_date(row.get("Data", "")),
                "descrizione": row.get("Descrizione", "").strip(),
                "categoria": row.get("Categoria", "").strip(),
                "importo": round_money(amount),
                "pagato_da": payer,
                "partecipanti": names,
                "numero_partecipanti": count,
                "quota_per_partecipante": round_money(quota),
                "note": row.get("Note", "").strip(),
            }
        )

    paid = {name: 0.0 for name in participant_order}
    total_versamenti = 0.0

    for row in versamenti:
        name = normalize_name(row.get("Partecipante", ""))
        amount = parse_money(row.get("Importo (€)", ""))

        if not name and amount == 0:
            continue

        if name and name not in paid:
            paid[name] = 0.0
            consumed[name] = 0.0
            participant_order.append(name)

        if name:
            paid[name] += amount

        total_versamenti += amount

    partecipanti = []
    for name in participant_order:
        versato = paid.get(name, 0.0)
        consumato = consumed.get(name, 0.0)
        saldo = versato - consumato

        partecipanti.append(
            {
                "nome": name,
                "versato": round_money(versato),
                "consumato": round_money(consumato),
                "saldo": round_money(saldo),
            }
        )

    # Ultime spese: dalla più recente alla più vecchia.
    movement_records.sort(
        key=lambda x: date_sort_key(x["data"]), reverse=True
    )

    data = {
        "generato_il": datetime.now().astimezone().isoformat(timespec="seconds"),
        "saldo_cassa": round_money(total_versamenti - total_spese),
        "totale_versamenti": round_money(total_versamenti),
        "totale_spese": round_money(total_spese),
        "numero_partecipanti": len(partecipanti),
        "partecipanti": partecipanti,
        "ultime_spese": movement_records,
    }

    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Esporta Cassa Comune da ODS a JSON."
    )
    parser.add_argument(
        "ods",
        nargs="?",
        default="Cassa_Comune_Partecipanti.ods",
        help="Percorso del file ODS",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="web/dati.json",
        help="Percorso del JSON di output",
    )

    args = parser.parse_args()

    try:
        data = export_ods(Path(args.ods), Path(args.output))

        print("Esportazione completata.")
        print(f"  Saldo cassa:       € {data['saldo_cassa']:.2f}")
        print(f"  Versamenti:        € {data['totale_versamenti']:.2f}")
        print(f"  Spese:             € {data['totale_spese']:.2f}")
        print(f"  Partecipanti:      {data['numero_partecipanti']}")
        print(f"  Output:            {args.output}")

        return 0

    except Exception as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
