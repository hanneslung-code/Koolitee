# Koolitee kaaslane – toimiv pilootkeskkond

See projekt on serveripoolse loogikaga veebirakendus, mitte staatiline HTML-prototüüp. Rakendus salvestab kasutajad ja vestlused SQLite-andmebaasi, haldab sisselogimist, saadab lapsevanema kinnituskirju ning saadab teavitusi kutsete ja uute sõnumite kohta.

## 1. Käivitamine Windowsis

**Lihtsaim viis:**

1. Paigalda ja käivita [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Paki see ZIP-fail arvutis lahti.
3. Ava kaust `koolitee-kaaslane`.
4. Tee failist `.env.example` koopia nimega `.env`.
5. Ava `.env` ja pane `SECRET_KEY` reale pikk juhuslik salasõna (soovitavalt vähemalt 40 juhuslikku märki).
6. Tee topeltklõps failil `Käivita-Windows.bat` või ava selles kaustas terminal ja käivita:

   ```bash
   docker compose up --build
   ```

Kui käivitamine õnnestub, ava:

- **Veebileht:** http://localhost:8000
- **Test-e-postkast:** http://localhost:8025

Esimesel käivitamisel ehitab Docker rakenduse ja loob andmebaasi automaatselt. Hoia terminaliaken töötamise ajal avatuna.

Peatamiseks vajuta terminalis `Ctrl+C` ja käivita soovi korral `docker compose down`. Andmebaas jääb alles ka pärast konteinerite peatamist (Docker haldab seda püsiva andmemahuna).

## 2. Kuidas kahe lapse kontoga kogu voogu testida

1. Ava veebileht ja vali **Loo konto**.
2. Loo esimene testkonto (näiteks kasutajanimi `mari123`, kool `Tallinna Mustamäe Gümnaasium`, piirkond `Mustamäe`, asum `Sääse`). Kasuta testimiseks enda kontrollitavat e-posti aadressi.
3. Ava test-e-postkast aadressil http://localhost:8025. Seal on lapsevanema kinnituskiri. Ava kirjas olev link ja vajuta kinnituslehel konto aktiveerimise nuppu.
4. Loo teine konto (näiteks `mart456`) sama kooli ja piirkonnaga. Võid kasutada sama test-e-posti aadressi: igal kontol on eraldi kasutajanimi, e-post jääb privaatseks.
5. Logi esimese kontoga sisse ühes brauseris ja teise kontoga teises brauseris või inkognito-aknas. Nii saad korraga kahe lapse vaates tegutseda.
6. Saada ühelt kontolt teisele kutse. Kontrolli Mailpiti postkastist teavituskirja.
7. Võta teise kontoga kutse vastu. Esimese konto lapsevanema aadressile saadetakse vastuvõtmise teavitus.
8. Ava vestlus, saada sõnum ja kontrolli, et teise konto lapsevanema postkasti saabub uue sõnumi teavitus. Sõnumi sisu e-kirjas ei kuvata.

Mailpit on kohalik testpostkast: see püüab rakenduse e-kirjad kinni ega saada neid päris e-posti aadressidele edasi. Nii saab kogu e-posti voo läbi katsetada ilma SMTP-kontot seadistamata.

## 3. Mida rakendus praegu teeb

- Registreerimine lapse eesnime, kasutajanime, kooli, linnaosa/valda, asumi/asula, liikumisviisi ja lapsevanema e-postiga.
- Liikumisviisid: jalgsi, rattaga, bussiga ja autoga.
- Kasutajanimi ja parool; salasõna salvestatakse räsina, mitte avatava tekstina.
- Kõigi kontode aktiveerimine lapsevanema/eestkostja e-kirja kinnituse järel.
- Lapsevanema e-posti ei kuvata teistele kasutajatele.
- Koolikaaslaste leidmine sama kooli ning sama linnaosa/valla alusel; sama asumi/asula kasutajad kuvatakse eespool.
- Kutse saatmine, vastuvõtmine ja tagasilükkamine.
- Vestlus avaneb alles pärast kutse vastuvõtmist.
- Lapsevanema e-posti teavitused uue kutse, kutse vastuvõtmise ja uue sõnumi kohta.
- E-posti aadresside, telefoninumbrite ja veebiaadresside saatmise lihtne automaatne tõkestus vestluses.
- Kasutaja blokeerimine, sobimatu käitumise raporteerimine ja konto kustutamine.
- Raport saadetakse ka moderaatori e-postile, kui `MODERATION_EMAIL` on seadistatud.
- Täpseid koduaadresse, koordinaate ega asukohajälgimist ei koguta.

## 4. Piirkonnad ja koolid

Tallinna valikus on kaheksa linnaosa asumid; lisaks on eraldi Harjumaa valdade ja lähiümbruse asulate valikud. Kui kooli nimekirjas ei ole, vali **Muu kool (sisesta nimi)**. Sama sisestatud koolinimega kontod saavad omavahel vasteid.

Koolide loend on alustamiseks ulatuslik, kuid see ei ole automaatselt riikliku haridusregistriga sünkroonis. Enne avalikku käivitamist tuleb koolide ametlikud nimed ja tegutsevate koolide täielik loend Haridusregistri / Tallinna Haridusameti andmetega üle kontrollida.

## 5. Päris e-kirjade saatmine

Kohalik katsetus kasutab Mailpitit. Päris e-kirjade saatmiseks tuleb kasutada e-posti teenusepakkuja SMTP-andmeid. Ava `docker-compose.yml` ja muuda teenuse `web` keskkonnamuutujaid, näiteks:

```yaml
SMTP_HOST: smtp.example.com
SMTP_PORT: 587
SMTP_USER: sinu-smtp-kasutaja
SMTP_PASSWORD: sinu-smtp-parool
SMTP_STARTTLS: "true"
SMTP_FROM: Koolitee kaaslane <no-reply@sinudomeen.ee>
MODERATION_EMAIL: haldaja@sinudomeen.ee
```

Asenda näidisväärtused enda teenusepakkuja andmetega ning määra `BASE_URL` avaliku veebiaadressina. Ära pane SMTP-paroole avalikku Git-hoidlasse.

## 6. Avalikuks kasutamiseks vajalikud tööd

See on töötav tehniline piloot, kuid laste pärisandmetega avalikku teenusesse avamiseks ei piisa ainult koodi käivitamisest. Enne avalikku käivitamist tuleb vähemalt:

- määrata teenuse vastutav töötleja, avaldada privaatsusteade, kasutustingimused ja säilitustähtajad;
- teha andmekaitsealane mõjuhinnang (DPIA) ja leppida kokku andmete kustutamise/varundamise kord;
- kontrollida lapsevanema nõusoleku andmise protsessi tegelikku toimivust ning lisada vanemale võimalus nõusolek tagasi võtta;
- määrata päris moderaator, kes raporteid jälgib ja neile reageerib;
- lisada tootmiskeskkonnas HTTPS, tugev salavõti, regulaarne turvauuendamine, varundus ja taastamise test;
- lasta rakendus turva- ja kasutatavustestiga üle kontrollida ning teha koolide/linnaosade loend ametlike allikatega ajakohaseks.

Eesti isikuandmete kaitse seaduse § 8 järgi on infoühiskonna teenuse puhul lapse enda nõusoleku vanusepiir 13 aastat; alla 13-aastase lapse andmeid võib sellel alusel töödelda seadusliku esindaja nõusolekul. See rakendus küsib vanema/eestkostja kinnituse kõigilt kontodelt rangema turvavalikuna. See tehniline kinnitusvoog ei asenda enne avalikku käivitamist õiguslikku kontrolli ega nõusoleku piisava kontrollimise korraldust.

## 7. Olulised tehnilised märkused

- Rakendus kasutab Flaski, SQLite'i ja serveripoolseid sessioone (Flaski allkirjastatud sessiooniküpsis).
- Andmebaas asub Dockeri püsivas andmemahus `koolitee_data` ja säilib konteinerite taaskäivitamisel.
- Kõik vormid kasutavad CSRF-tokenit; paroolid räšitakse; päringud kasutavad SQL parameetreid.
- Turvalisuse HTTP-päised ja piiratud sisupoliitika on seadistatud. Tootmises tuleb kasutada HTTPS-i ning `APP_ENV=production`.
- Andmebaasi nullimiseks peata rakendus käsuga `docker compose down -v` ning käivita uuesti `docker compose up --build`. See kustutab kõik testkontod ja vestlused.

## Allikad lähteandmete kontrolliks

- Tallinna geoportaal: linnaosade ja asumite piirid – https://www.tallinn.ee/est/geoportaal/Tallinna-linnaosade-ja-asumite-piirid
- Tallinna Haridusamet: koolide nimekiri – https://www.tallinn.ee/et/haridusasutused/koolid
- Haridus- ja Teadusministeeriumi haridusregister / teatmik – https://teatmik.haridus.ee/schools/
- Isikuandmete kaitse seadus – https://www.riigiteataja.ee/en/akt/519032026002
