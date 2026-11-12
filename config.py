"""Seed data for Tallinn and nearby Harju County schools and neighbourhoods."""

REGIONS = {
    "Haabersti": ["Astangu", "Haabersti", "Kakumäe", "Mäeküla", "Mustjõe", "Pikaliiva", "Rocca al Mare", "Tiskre", "Veskimetsa", "Vismeistri", "Väike-Õismäe", "Õismäe"],
    "Kesklinn": ["Aegna", "Juhkentali", "Kadriorg", "Kassisaba", "Keldrimäe", "Kitseküla", "Kompassi", "Luite", "Maakri", "Mõigu", "Raua", "Sadama", "Sibulaküla", "Südalinn", "Tatari", "Torupilli", "Tõnismäe", "Uus Maailm", "Vanalinn", "Veerenni", "Ülemistejärve"],
    "Kristiine": ["Järve", "Lilleküla", "Tondi"],
    "Lasnamäe": ["Katleri", "Kurepõllu", "Kuristiku", "Laagna", "Loopealse", "Mustakivi", "Pae", "Paevälja", "Priisle", "Seli", "Sikupilli", "Sõjamäe", "Tondiraba", "Uuslinn", "Väo", "Ülemiste"],
    "Mustamäe": ["Kadaka", "Mustamäe", "Siili", "Sääse"],
    "Nõmme": ["Hiiu", "Kivimäe", "Laagri", "Liiva", "Männiku", "Nõmme", "Pääsküla", "Rahumäe", "Raudalu", "Vana-Mustamäe"],
    "Pirita": ["Iru", "Kloostrimetsa", "Kose", "Laiaküla", "Lepiku", "Maarjamäe", "Merivälja", "Mähe", "Pirita"],
    "Põhja-Tallinn": ["Kalamaja", "Karjamaa", "Kelmiküla", "Kopli", "Merimetsa", "Paljassaare", "Pelgulinn", "Pelguranna", "Sitsi"],
    "Viimsi vald": ["Haabneeme", "Viimsi alevik", "Püünsi", "Pringi", "Randvere", "Lubja", "Leppneeme", "Miiduranna", "Kelvingi", "Metsakasti", "Rohuneeme", "Äigrumäe", "Laiaküla"],
    "Rae vald": ["Peetri alevik", "Jüri alevik", "Assaku alevik", "Lagedi alevik", "Vaida alevik", "Kurna", "Rae küla", "Vaskjala", "Suursoo", "Patika"],
    "Harku vald": ["Tabasalu alevik", "Harku alevik", "Muraste", "Vääna-Jõesuu", "Türisalu", "Ilmandu", "Rannamõisa", "Suurupi", "Vääna", "Tutermaa", "Kumna"],
    "Saue vald": ["Laagri alevik", "Saue linn", "Vanamõisa", "Alliku", "Ääsmäe", "Kiia", "Hüüru", "Valingu", "Tuula", "Maidla"],
    "Jõelähtme vald": ["Loo alevik", "Kostivere alevik", "Neeme", "Jägala", "Ihasalu", "Kaberneeme", "Ülgase", "Rebala"],
    "Maardu linn": ["Maardu", "Muuga"],
    "Saku vald": ["Saku alevik", "Kiisa alevik", "Kasemetsa", "Üksnurme"],
    "Kiili vald": ["Kiili alev", "Vaela", "Luige", "Kangru"],
    "Keila linn": ["Keila"],
    "Kose vald": ["Kose alevik", "Ravila alevik", "Habaja"],
    "Anija vald": ["Kehra linn", "Alavere", "Aegviidu alev"],
    "Lääne-Harju vald": ["Paldiski linn", "Laulasmaa", "Vasalemma", "Padise"],
    "Loksa linn": ["Loksa"],
    "Raasiku vald": ["Raasiku alevik", "Aruküla alevik", "Peningi", "Perila"],
    "Kuusalu vald": ["Kuusalu alevik", "Kiiu alevik", "Kolga", "Vihasoo", "Hara"],
}

# This list is a practical starting register for general-education schools in Tallinn
# and the neighbouring Harju County area. Verify it against the Education Register
# before opening registration to the public; schools and names can change.
SCHOOLS = sorted(set([
    # Tallinn municipal general education schools
    "Ehte Humanitaargümnaasium", "Gustav Adolfi Gümnaasium", "Haabersti Vene Gümnaasium",
    "Hiiu Kool", "Jakob Westholmi Gümnaasium", "Kadrioru Saksa Gümnaasium",
    "Kalamaja Põhikool", "Karjamaa Põhikool", "Kivimäe Põhikool",
    "Lasnamäe Gümnaasium", "Lasnamäe Põhikool", "Lasnamäe Vene Gümnaasium",
    "Merivälja Kool", "Pelgulinna Gümnaasium", "Pirita Majandusgümnaasium",
    "Ristiku Põhikool", "Tallinna 21. Kool", "Tallinna 32. Keskkool",
    "Tallinna 53. Keskkool", "Tallinna Arte Gümnaasium", "Tallinna Haabersti Gümnaasium",
    "Tallinna Heleni Kool", "Tallinna Humanitaargümnaasium", "Tallinna Inglise Kolledž",
    "Tallinna Juudi Kool", "Tallinna Järveotsa Gümnaasium", "Tallinna Kadaka Põhikool",
    "Tallinna Kesklinna Vene Gümnaasium", "Tallinna Kunstigümnaasium",
    "Tallinna Kuristiku Gümnaasium", "Tallinna Laagna Gümnaasium",
    "Tallinna Lilleküla Gümnaasium", "Tallinna Linnamäe Vene Lütseum",
    "Tallinna Läänemere Gümnaasium", "Tallinna Mahtra Põhikool",
    "Tallinna Merekalda Kool", "Tallinna Mustamäe Gümnaasium",
    "Tallinna Mustamäe Humanitaargümnaasium", "Tallinna Mustamäe Reaalgümnaasium",
    "Tallinna Mustjõe Gümnaasium", "Tallinna Nõmme Gümnaasium", "Tallinna Nõmme Põhikool",
    "Tallinna Pae Gümnaasium", "Tallinna Prantsuse Lütseum", "Tallinna Pääsküla Gümnaasium",
    "Tallinna Rahumäe Põhikool", "Tallinna Reaalkool", "Tallinna Saksa Gümnaasium",
    "Tallinna Sikupilli Keskkool", "Tallinna Südalinna Kool", "Tallinna Tehnikagümnaasium",
    "Tallinna Tondi Põhikool", "Tallinna Tõnismäe Reaalkool", "Tallinna Ühisgümnaasium",
    "Tallinna Avatud Kool", "Tallinna Laagna Lasteaed-Põhikool",
    "Tallinna Kristiine Gümnaasium", "Tallinna Õismäe Gümnaasium", "Tallinna Õismäe Vene Lütseum",
    "Tallinna Ranniku Gümnaasium", "Tallinna Pääsküla Kool", "Tallinna Põhjatähe Põhikool",
    "Tallinna Konstantin Pätsi Vabaõhukool", "Tallinna 37. Keskkool", "Tallinna Juhkentali Gümnaasium",
    "Tallinna Vabaduse Kool", "Tallinna Pelgulinna Riigigümnaasium", "Tallinna Mustamäe Riigigümnaasium",
    "Tallinna Muusikakeskkool", "Tallinna Balletikool", "Audentese Spordigümnaasium",
    # Tallinn private / international schools
    "Audentese Erakool", "Avatud Kool", "EBS Gümnaasium", "Gaia Kool", "Kaarli Kool",
    "Nõmme Erakool", "Rocca al Mare Kool", "Tallinna Erakool", "Tallinna Vaba Waldorfkool",
    "Vanalinna Hariduskolleegium", "Vivere Kool", "Püha Johannese Kool",
    "International School of Estonia", "International School of Tallinn", "Tallinna Euroopa Kool",
    "Tallinna Rahvusvaheline Kool", "Eurogümnaasium", "Emili Kool", "Tallinna Toomkool",
    "Erakool Garant", "Loova Tuleviku Kool", "Mäepealse Erakool", "Hilariuse Kool",
    "Sakala Eragümnaasium", "Tallinna Täiskasvanute Gümnaasium",
    # Nearby Harju County schools
    "Haabneeme Kool", "Püünsi Kool", "Randvere Kool", "Viimsi Kool", "Viimsi Gümnaasium",
    "Jüri Gümnaasium", "Peetri Lasteaed-Põhikool", "Kindluse Kool", "Rae Gümnaasium",
    "Loo Keskkool", "Kostivere Kool", "Tabasalu Kool", "Tabasalu Gümnaasium",
    "Harkujärve Põhikool", "Laagri Kool", "Saue Kool", "Saku Gümnaasium",
    "Kiili Gümnaasium", "Keila Kool", "Maardu Gümnaasium", "Maardu Põhikool",
    "Kose Gümnaasium", "Kehra Gümnaasium", "Paldiski Ühisgümnaasium",
    "Loksa Gümnaasium", "Raasiku Põhikool", "Aruküla Põhikool", "Kuusalu Keskkool", "Kolga Kool",
]))

MODES = ["Jalgsi", "Rattaga", "Bussiga", "Autoga"]
