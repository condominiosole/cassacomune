/* =========================================================
   CASSA COMUNE - APP
   ========================================================= */

"use strict";


/* =========================================================
   CONFIGURAZIONE
   ========================================================= */

const DATA_FILE = "dati.json";


/* =========================================================
   FORMATTAZIONE
   ========================================================= */

function formatEuro(value) {

    const number = Number(value) || 0;

    return new Intl.NumberFormat("it-IT", {
        style: "currency",
        currency: "EUR"
    }).format(number);

}


function formatNumber(value) {

    const number = Number(value) || 0;

    return new Intl.NumberFormat("it-IT", {
        maximumFractionDigits: 2
    }).format(number);

}


/* =========================================================
   ELEMENTI HTML
   ========================================================= */

function getElement(id) {

    return document.getElementById(id);

}


/* =========================================================
   AGGIORNA RIEPILOGO
   ========================================================= */

function aggiornaRiepilogo(data) {

    const saldo = Number(data.saldo_cassa) || 0;
    const versamenti = Number(data.totale_versamenti) || 0;
    const spese = Number(data.totale_spese) || 0;

    const partecipanti =
        Array.isArray(data.partecipanti)
            ? data.partecipanti.length
            : 0;


    const saldoElement = getElement("saldoCassa");

    if (saldoElement) {

        saldoElement.textContent =
            formatEuro(saldo);

        saldoElement.classList.remove(
            "saldo-positivo",
            "saldo-negativo"
        );

        if (saldo > 0) {

            saldoElement.classList.add(
                "saldo-positivo"
            );

        } else if (saldo < 0) {

            saldoElement.classList.add(
                "saldo-negativo"
            );

        }

    }


    const versamentiElement =
        getElement("totVersamenti");

    if (versamentiElement) {

        versamentiElement.textContent =
            formatEuro(versamenti);

    }


    const speseElement =
        getElement("totSpese");

    if (speseElement) {

        speseElement.textContent =
            formatEuro(spese);

    }


    const partecipantiElement =
        getElement("numPartecipanti");

    if (partecipantiElement) {

        partecipantiElement.textContent =
            formatNumber(partecipanti);

    }

}


/* =========================================================
   TABELLA PARTECIPANTI
   ========================================================= */

function aggiornaPartecipanti(data) {

    const table =
        getElement("tblPartecipanti");

    if (!table) {
        return;
    }


    const tbody =
        table.querySelector("tbody");

    if (!tbody) {
        return;
    }


    tbody.innerHTML = "";


    if (
        !Array.isArray(data.partecipanti) ||
        data.partecipanti.length === 0
    ) {

        const row =
            document.createElement("tr");

        const cell =
            document.createElement("td");

        cell.colSpan = 4;

        cell.className = "empty";

        cell.textContent =
            "Nessun partecipante disponibile.";

        row.appendChild(cell);

        tbody.appendChild(row);

        return;
    }


    /*
     * Ordina i partecipanti alfabeticamente.
     * Il nome viene confrontato senza distinguere
     * maiuscole/minuscole.
     */

    const partecipanti =
        [...data.partecipanti].sort(
            (a, b) =>
                String(a.nome || "").localeCompare(
                    String(b.nome || ""),
                    "it",
                    {
                        sensitivity: "base"
                    }
                )
        );


    partecipanti.forEach(partecipante => {

        const row =
            document.createElement("tr");


        /* Nome */

        const nomeCell =
            document.createElement("td");

        nomeCell.textContent =
            partecipante.nome || "-";

        row.appendChild(nomeCell);


        /* Versato */

        const versatoCell =
            document.createElement("td");

        versatoCell.className =
            "importo";

        versatoCell.textContent =
            formatEuro(
                partecipante.versato
            );

        row.appendChild(versatoCell);


        /* Consumato */

        const consumatoCell =
            document.createElement("td");

        consumatoCell.className =
            "importo";

        consumatoCell.textContent =
            formatEuro(
                partecipante.consumato
            );

        row.appendChild(consumatoCell);


        /* Saldo */

        const saldoCell =
            document.createElement("td");

        const saldo =
            Number(partecipante.saldo) || 0;


        const saldoBadge =
            document.createElement("span");


        if (saldo > 0) {

            saldoBadge.className =
                "saldo-positivo";

        } else if (saldo < 0) {

            saldoBadge.className =
                "saldo-negativo";

        }


        saldoBadge.textContent =
            formatEuro(saldo);


        saldoCell.appendChild(
            saldoBadge
        );

        row.appendChild(saldoCell);


        tbody.appendChild(row);

    });

}


/* =========================================================
   TABELLA SPESE
   ========================================================= */

function aggiornaSpese(data) {

    const table =
        getElement("tblSpese");

    if (!table) {
        return;
    }


    const tbody =
        table.querySelector("tbody");

    if (!tbody) {
        return;
    }


    tbody.innerHTML = "";


    /*
     * Supportiamo sia:
     *
     * data.ultime_spese
     *
     * sia:
     *
     * data.movimenti
     */

    let spese =
        Array.isArray(data.ultime_spese)
            ? data.ultime_spese
            : data.movimenti;


    if (!Array.isArray(spese)) {

        spese = [];

    }


    if (spese.length === 0) {

        const row =
            document.createElement("tr");

        const cell =
            document.createElement("td");

        cell.colSpan = 5;

        cell.className = "empty";

        cell.textContent =
            "Nessuna spesa disponibile.";

        row.appendChild(cell);

        tbody.appendChild(row);

        return;
    }


    /*
     * Mostriamo prima le spese più recenti.
     *
     * Se il JSON contiene una data riconoscibile,
     * viene usata per l'ordinamento.
     */

    const speseOrdinate =
        [...spese].sort((a, b) => {

            const dataA =
                new Date(a.data || 0);

            const dataB =
                new Date(b.data || 0);

            return dataB - dataA;

        });


    speseOrdinate.forEach(spesa => {

        const row =
            document.createElement("tr");


        /* Data */

        const dataCell =
            document.createElement("td");

        dataCell.className = "data";

        dataCell.textContent =
            spesa.data || "-";

        row.appendChild(dataCell);


        /* Descrizione */

        const descrizioneCell =
            document.createElement("td");

        descrizioneCell.textContent =
            spesa.descrizione || "-";

        row.appendChild(
            descrizioneCell
        );


        /* Categoria */

        const categoriaCell =
            document.createElement("td");

        categoriaCell.textContent =
            spesa.categoria || "-";

        row.appendChild(
            categoriaCell
        );


        /* Importo */

        const importoCell =
            document.createElement("td");

        importoCell.className =
            "importo";

        importoCell.textContent =
            formatEuro(
                spesa.importo
            );

        row.appendChild(
            importoCell
        );


        /* Pagato da */

        const pagatoCell =
            document.createElement("td");

        pagatoCell.textContent =
            spesa.pagato_da || "-";

        row.appendChild(
            pagatoCell
        );


        tbody.appendChild(row);

    });

}


/* =========================================================
   CARICAMENTO DATI
   ========================================================= */

async function caricaDati() {

    try {

        const response =
            await fetch(
                DATA_FILE,
                {
                    cache: "no-store"
                }
            );


        if (!response.ok) {

            throw new Error(
                `Errore HTTP ${response.status}`
            );

        }


        const data =
            await response.json();


        aggiornaRiepilogo(data);

        aggiornaPartecipanti(data);

        aggiornaSpese(data);


        console.log(
            "Dati caricati correttamente."
        );


    } catch (error) {

        console.error(
            "Errore caricamento dati:",
            error
        );


        mostraErrore(
            "Impossibile caricare i dati della cassa."
        );

    }

}


/* =========================================================
   MESSAGGIO DI ERRORE
   ========================================================= */

function mostraErrore(messaggio) {

    const main =
        document.querySelector("main");

    if (!main) {
        return;
    }


    const existing =
        document.querySelector(".error");

    if (existing) {
        existing.remove();
    }


    const errorBox =
        document.createElement("div");

    errorBox.className =
        "error";

    errorBox.textContent =
        messaggio;


    main.insertBefore(
        errorBox,
        main.firstChild
    );

}


/* =========================================================
   AVVIO
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        caricaDati();

    }
);