"""
Extractor for pathomorphological nosodes (Table, pages 246-252).
Conditions with their Latin names grouped by disease category.
"""
import sqlite3

from .base import BaseExtractor


# Hard-coded data from OCR (pages 246-252)
# Format: (condition_name, condition_name_lat, disease_category, source_page)
PATHOMORPHOLOGICAL_DATA: list[tuple[str, str | None, str, int]] = [
    # === ЗАБОЛЕВАНИЯ ЛИМФОИДНЫХ ФОЛЛИКУЛОВ МИНДАЛИН ===
    ("Абсцесс лимфатического узла", "Lymphknotenabszess", "tonsil_lymphoid", 246),
    ("Ангина Плаут-Винцента", "Angina Plaut Vincent", "tonsil_lymphoid", 246),
    ("Инфицированная лимфа", "Infizierte Lymphe", "tonsil_lymphoid", 246),
    ("Тонзиллярный абсцесс", "Tonsillarabszess", "tonsil_lymphoid", 246),
    ("Фолликулярная ангина", "Angina follicularis", "tonsil_lymphoid", 246),
    ("Хронический тонзиллит", "Chron. Tonsillitis", "tonsil_lymphoid", 246),
    ("Хрон. гиперпластич. тонзиллит", "Chron. Hyperpl. Tonsillitis", "tonsil_lymphoid", 246),

    # === ЗАБОЛЕВАНИЯ ОРГАНОВ СЛУХА ===
    ("Лимфорея (наружный отит)", "Lymphorrhoe", "ear", 246),
    ("Мастоидит", "Mastoiditis", "ear", 246),
    ("Полип слухового прохода", "Ohrenpolyp", "ear", 246),
    ("Холестеатома", "Cholesteatom", "ear", 246),

    # === ЗАБОЛЕВАНИЯ ПРИДАТОЧНЫХ ПАЗУХ НОСА ===
    ("Аденоидные вегетации", "Nasenmuschelhyperplasie", "sinus", 246),
    ("Гайморит", "Sinusitis max", "sinus", 246),
    ("Киста гайморовой пазухи", "Kieferhohlencyste", "sinus", 246),
    ("Лейкоплакия", "Lymphoplaques", "sinus", 246),
    ("Остеосинусит гайморовой пазухи", "Osteo-Sinusitis max", "sinus", 246),
    ("Полип гайморовой пазухи", "Kieferhohlenpolyp", "sinus", 246),
    ("Полипоз этмоидальной пазухи", "Siebbeinpolypen", "sinus", 246),
    ("Фронтит", "Sinusitis front", "sinus", 246),

    # === ЗАБОЛЕВАНИЯ ОКОЛОУШНЫХ ЖЕЛЕЗ ===
    ("Камень слюнной околоушной железы", "Parotis-Zahnstein", "parotid", 246),
    ("Паротит", "Parotitis", "parotid", 246),
    ("Цилиндрома околоушной железы", "Parotis Zylindrom", "parotid", 246),

    # === ЗАБОЛЕВАНИЯ ЗУБОВ И СЛИЗИСТЫХ ПОЛОСТИ РТА ===
    ("Воспаление зубодесенного кармана", "Zahnfleischtasche", "dental", 246),
    ("Гангренозная гранулема", "Gangran-Granulom", "dental", 246),
    ("Гангренозная пульпа", "Gangrenose Pulpa", "dental", 246),
    ("Гингивит", "Gingivitis", "dental", 246),
    ("Гранулема корня зуба", "Zahnwurzelgranulom", "dental", 246),
    ("Гранулематозная ткань периодонта", "Destr. Granulat. Gewebe", "dental", 246),
    ("Диабетическая пародонтопатия", "Diabetische parodontose", "dental", 246),
    ("Жировой дистрофический остит", "Fettige Kieferostitis", "dental", 246),
    ("Зубная фистула", "Zahnfistel", "dental", 247),
    ("Зубные камни", "Zahnsteinkonkremente", "dental", 247),
    ("Кариес", "Karies", "dental", 247),
    ("Некротический гингивит", "Nekrotisierende Gingivitis", "dental", 247),
    ("Некротический остит нижней челюсти", "Unterkieferostitis", "dental", 247),
    ("Одонтогенный абсцесс", "Odontogener Fundusabszess", "dental", 247),
    ("Остеосклероз челюстей", "Osteosclerose des Kiefers", "dental", 247),
    ("Острый бактериальный остит челюсти", "Akute bakterielle Kieferostitis", "dental", 247),
    ("Острый пульпит", "Akute Pulpitis", "dental", 247),
    ("Папиллома рта", "Mundpapillom", "dental", 247),
    ("Пародонтоз", "Parodontose", "dental", 247),
    ("Парулис стафилококковый (флюс)", "Parulis (Staph. aureus)", "dental", 247),
    ("Парулис стрептококковый (флюс)", "Parulis (Streptoc. muc.)", "dental", 247),
    ("Периодонтит", "Periodontitis", "dental", 247),
    ("Периостит", "Kieferostitis", "dental", 247),
    ("Плоскоклеточная эпителиальная киста", "Plattenepithelcyste", "dental", 247),
    ("Склерозирующий остит", "Sclerosierende Ostitis", "dental", 247),
    ("Стоматит", "Stomatitis", "dental", 247),
    ("Фиброма зубодесневого кармана", "Zahnfleischfibrom", "dental", 247),
    ("Фолликулярная киста", "Folliculare Cyste", "dental", 247),
    ("Хронический пульпит", "Chronische Pulpitis", "dental", 247),
    ("Хронический бактериальный остит", "Chronische bakterielle Kieferostitis", "dental", 247),
    ("Экссудативный остит", "Exsudative Ostitis", "dental", 247),
    ("Эпулюс", "Epulis", "dental", 247),
    ("Язвенный гингивит", "Ulcerose Gingivitis", "dental", 247),

    # === ЗАБОЛЕВАНИЯ ОРГАНОВ ЗРЕНИЯ ===
    ("Бурая катаракта", "Cataracta brunescens", "eye", 247),
    ("Конъюнктивит", "Conjunctivitis", "eye", 247),
    ("Осложненная катаракта", "Cataracta complicata", "eye", 247),
    ("Старческая катаракта", "Cataracta senilis", "eye", 247),
    ("Фолликулярный конъюнктивит", "Conjunctivitis follicularis", "eye", 247),
    ("Халязион", "Chalazion", "eye", 247),

    # === ЗАБОЛЕВАНИЯ ГОРТАНИ И ГЛОТКИ ===
    ("Ларингит", "Laryngitis", "larynx_pharynx", 247),
    ("Фарингит", "Pharyngitis", "larynx_pharynx", 247),
    ("Папиллома гортани", "Larynxpapillom", "larynx_pharynx", 247),

    # === ЗАБОЛЕВАНИЯ БРОНХОЛЕГОЧНОЙ СИСТЕМЫ ===
    ("Болезнь Бека", "Morbus Boeck", "respiratory", 247),
    ("Бронхиальная астма", "Asthma bronchiale", "respiratory", 247),
    ("Бронхоэктатическая болезнь", "Bronchiektasie", "respiratory", 247),
    ("Плеврит", "Pleuritis", "respiratory", 247),

    # === ЗАБОЛЕВАНИЯ ЖКТ ===
    ("Аппендицит", "Appendicitis", "digestive", 247),
    ("Болезнь Крона", "Morbus Crohn", "digestive", 247),
    ("Дивертикул Меккеля", "Meckel'scher Divertikel", "digestive", 247),
    ("Дивертикулез", "Diverticulose", "digestive", 247),
    ("Мезаденит", "Mesadenitis", "digestive", 247),
    ("Некротический аппендицит", "Appendicitis necroticans", "digestive", 248),
    ("Перитонит", "Peritonitis", "digestive", 248),
    ("Сигмоидит", "Sigmoiditis", "digestive", 248),
    ("Стеноз поперечноободочной кишки", "Colon transversum sten", "digestive", 248),
    ("Хронический аппендицит", "Chronische Appendicitis", "digestive", 248),
    ("Хронический колит", "Chron. colitis", "digestive", 248),
    ("Язва 12-перстной кишки", "Ulcus duodeni", "digestive", 248),
    ("Полипоз желудка", "Magenpolyposis", "digestive", 248),
    ("Эрозивный гастрит", "Ventriculus Ulcus", "digestive", 248),
    ("Язва желудка", "Ulcus ventriculi", "digestive", 248),
    ("Геморрой", "Haemorrhoiden", "digestive", 248),
    ("Перипроктит", "Periproktitischer Abszess", "digestive", 248),
    ("Полип прямой кишки", "Rectum polyp", "digestive", 248),
    ("Хронический проктит", "Cronische Proctitis", "digestive", 248),

    # === ЗАБОЛЕВАНИЯ ПЕЧЕНИ И ЖЕЛЧНОГО ПУЗЫРЯ ===
    ("Асцит", "Ascites", "liver_biliary", 248),
    ("Билиарный цирроз печени", "Biliare Zirrhose", "liver_biliary", 248),
    ("Гепатолиенальный фиброз (б-нь Банти)", "Banti", "liver_biliary", 248),
    ("Гепатоцеребральная дистрофия (б-нь Вильсона)", "Wilson", "liver_biliary", 248),
    ("Цирроз портальный", "Leberzirrhose", "liver_biliary", 248),
    ("Гепатит", "Hepatitis", "liver_biliary", 248),
    ("Аденомиоз желчного пузыря", "Adenomyose Gallenblase", "liver_biliary", 248),
    ("Желчные камни", "Calculi biliaris", "liver_biliary", 248),
    ("Холецистит", "Cholecystitis", "liver_biliary", 248),

    # === ЗАБОЛЕВАНИЯ ПОЧЕК И МОЧЕВОГО ПУЗЫРЯ ===
    ("Гломерулонефрит", "Glomerulonephritis", "kidney_urinary", 248),
    ("Коралловидные камни", "Korallenausgusstein", "kidney_urinary", 248),
    ("Нефрит", "Nephritis", "kidney_urinary", 248),
    ("Нефроз", "Nephrose", "kidney_urinary", 248),
    ("Оксалатные камни", "Calculi renales oxalat", "kidney_urinary", 248),
    ("Оксалурия", "Oxalaturie", "kidney_urinary", 248),
    ("Пиелит", "Pielitis", "kidney_urinary", 248),
    ("Пиелонефрит", "Pyelonephritis", "kidney_urinary", 248),
    ("Почечные камни", "Calculi renales", "kidney_urinary", 248),
    ("Солитарная киста почек", "Solitarcyste (Niere)", "kidney_urinary", 248),
    ("Камни мочевого пузыря", "Calculi vesicales", "kidney_urinary", 248),
    ("Папиллома мочевого пузыря", "Blasenpapillom", "kidney_urinary", 248),
    ("Полип мочевого пузыря", "Blasenpolyp", "kidney_urinary", 248),
    ("Цистопиелит", "Cystopyelitis", "kidney_urinary", 248),

    # === ЗАБОЛЕВАНИЯ МУЖСКИХ ПОЛОВЫХ ОРГАНОВ ===
    ("Аденома простаты", "Prostata-Adenom", "male_genital", 249),
    ("Задний уретрит", "Urethritis post. Masc.", "male_genital", 249),
    ("Камни простаты", "Calculi prostatae", "male_genital", 249),
    ("Остроконечная кондилома", "Candilomata acuminata", "male_genital", 249),
    ("Периорхит", "Periorchitis", "male_genital", 249),
    ("Семинома", "Seminom", "male_genital", 249),
    ("Хронический простатит", "Chron. Prostatitis", "male_genital", 249),

    # === ГИНЕКОЛОГИЧЕСКИЕ ЗАБОЛЕВАНИЯ ===
    ("Аденома шейки матки", "Cervix-Adenom", "gynecological", 249),
    ("Аднексит", "Adnexitis", "gynecological", 249),
    ("Бели", "Fluor albus", "gynecological", 249),
    ("Вагинит", "Vaginitis", "gynecological", 249),
    ("Миома матки", "Myoma Uteri", "gynecological", 249),
    ("Овариальная киста", "Ovarialkystom", "gynecological", 249),
    ("Параметрит", "Stauungsmetritis", "gynecological", 249),
    ("Полип матки", "Uteruspolyp", "gynecological", 249),
    ("Полип шейки матки", "Cervixpolyp", "gynecological", 249),
    ("Тератома", "Teratom", "gynecological", 249),
    ("Эндометриоз", "Endometriose", "gynecological", 249),

    # === ЗАБОЛЕВАНИЯ МОЛОЧНОЙ ЖЕЛЕЗЫ ===
    ("Кистозная мастопатия", "Mastopathia cystica", "breast", 249),
    ("Фиброаденома молочной железы", "Fibroadenom Mamma", "breast", 249),
    ("Фиброзная мастопатия", "Mamma fibromastosis", "breast", 249),

    # === ЗАБОЛЕВАНИЯ ЩИТОВИДНОЙ ЖЕЛЕЗЫ ===
    ("Аденома щитовидной железы", "Struma nodosa (Adenom)", "thyroid", 249),
    ("Загрудинный зоб", "Struma retrosternalis", "thyroid", 249),
    ("Киста щитовидной железы", "Struma-Cyste", "thyroid", 249),
    ("Паренхиматозный зоб", "Struma parenchymatosa", "thyroid", 249),

    # === ЗАБОЛЕВАНИЯ НЕРВНОЙ СИСТЕМЫ ===
    ("Боковой амиотрофический склероз", "Lateralsklerose", "nervous_system", 249),
    ("Лейкоэнцефалит", "Leucoencephalitis", "nervous_system", 249),
    ("Менингеома", "Meningeom", "nervous_system", 249),
    ("Менингит", "Meningitis", "nervous_system", 249),
    ("Множественный склероз", "Multiple Sklerosi-MS", "nervous_system", 249),
    ("Невралгия", "Neuralgie", "nervous_system", 249),
    ("Нейроглиома", "Gliom", "nervous_system", 249),
    ("Прогрессирующая мышечная дистрофия", "PMD", "nervous_system", 249),
    ("Сирингомиелия", "Syringomyelie", "nervous_system", 249),
    ("Энцефалит", "Encephalitis", "nervous_system", 249),

    # === ЗАБОЛЕВАНИЯ СОСУДОВ ===
    ("Атеросклероз", "Arteriosklerose", "cardiovascular", 249),
    ("Гиперхолестеринемия", "Hypercholesterinaemie", "cardiovascular", 249),
    ("Элефантиаз (лимфостаз)", "Elephantiasis", "cardiovascular", 250),

    # === ЗАБОЛЕВАНИЯ КОЖИ ===
    ("Акне", "Acne", "skin", 250),
    ("Базалиома", "Basaliom", "skin", 250),
    ("Буллезный дерматит (с-м Лайела)", "Epidermolysis bullosa", "skin", 250),
    ("Вульгарная волчанка", "Lupus vulgaris", "skin", 250),
    ("Гидраденит", "Hidradenitis", "skin", 250),
    ("Контрактура Дюпюитрена", "Dupuytren", "skin", 250),
    ("Красная волчанка", "Lupus erythematodes", "skin", 250),
    ("Липома", "Lipom", "skin", 250),
    ("Мокнущая экзема", "Ekzema madidans", "skin", 250),
    ("Псориаз", "Psoriasis", "skin", 250),
    ("Рожа", "Impferysipel", "skin", 250),
    ("Узловое пруриго", "Prurigo nodularis", "skin", 250),
    ("Фиброма кожи", "Hautfibrom", "skin", 250),
    ("Экзема", "Ekzem", "skin", 250),

    # === ЗАБОЛЕВАНИЯ ОПОРНО-ДВИГАТЕЛЬНОГО АППАРАТА ===
    ("Инфекционный артрит", "Tonsillitis-Polyarthritis", "musculoskeletal", 250),
    ("Остеомиелит", "Osteomyelitis", "musculoskeletal", 250),
    ("Остеомиелосклероз", "Osteomyelosklerose", "musculoskeletal", 250),
    ("Подагра", "Arthritis urica", "musculoskeletal", 250),
    ("Полиартрит", "Polyarthritis", "musculoskeletal", 250),
    ("Ревматизм", "Rheuma", "musculoskeletal", 250),
    ("Ревматоидный полиартрит", "Polyarthritis rheumatoid", "musculoskeletal", 250),
    ("Серозный гонит", "Seroser Kniegelenkerguss", "musculoskeletal", 250),
    ("Хронический миозит", "Chronische Myositis", "musculoskeletal", 250),

    # === БОЛЕЗНИ КРОВИ ===
    ("Апластическая анемия", "Aplastische Anamie", "blood", 250),
    ("Болезнь Верльгофа", "Werlhof", "blood", 250),
    ("Гемофилия", "Haemophilie", "blood", 250),
    ("Пернициозная анемия", "Perniciosa", "blood", 250),
    ("Лимфогранулематоз", "Lymphogranulomatose", "blood", 250),
    ("Полицитемия", "Polycythaemie", "blood", 250),

    # === НЕОПЛАСТИЧЕСКИЕ ЗАБОЛЕВАНИЯ (опухоли) ===
    ("Аденокарцинома желудка", "Adenocarcinoma ventriculi", "neoplastic", 250),
    ("Аденокарцинома прямой кишки", "Adenocarcinoma recti", "neoplastic", 250),
    ("Аденокарцинома сигмы", "Adenocarcinoma sigmae", "neoplastic", 250),
    ("Астроцитома", "Astrocitoma", "neoplastic", 250),
    ("Карцинома", "Carcinominum", "neoplastic", 251),
    ("Плоскоклеточный рак шейки матки", "Cervix-Plattenepithel", "neoplastic", 251),
    ("Хондросаркома", "Chondrosarcominum", "neoplastic", 251),
    ("Фибросаркома", "Fibrosarcominum", "neoplastic", 251),
    ("Рак печени", "Hepatocelulariscancer", "neoplastic", 251),
    ("Лимфолейкоз", "Lympholeucose", "neoplastic", 251),
    ("Лимфосаркома", "Lymphosarcomum", "neoplastic", 251),
    ("Аденокарцинома молочной железы", "Mamma Adenocarcinoma", "neoplastic", 251),
    ("Саркома молочной железы", "Mamma sarcom", "neoplastic", 251),
    ("Рак молочной железы", "Mamma scirrhosum", "neoplastic", 251),
    ("Меланома", "Melanom", "neoplastic", 251),
    ("Меланосаркома", "Melanosarcominum", "neoplastic", 251),
    ("Миелобластный лейкоз", "Myeloblasten Leukose", "neoplastic", 251),
    ("Миелоидный лейкоз", "Myeloische Leukose", "neoplastic", 251),
    ("Нейробластома", "Neuroblastoma", "neoplastic", 251),
    ("Нейрофиброма", "Neurofibroma", "neoplastic", 251),
    ("Нейрофибросаркома", "Neurofibrosarcoma", "neoplastic", 251),
    ("Гипернефроидный рак почек", "Niere hypernephroid", "neoplastic", 251),
    ("Олигодендроцитома", "Oligodendrocitoma", "neoplastic", 251),
    ("Плазмоцитома", "Plasmocytomum", "neoplastic", 251),
    ("Промиелоцитозный лейкоз", "Promyelocyt. Leucose", "neoplastic", 251),
    ("Опухоль простаты", "Prostata cribriformis", "neoplastic", 252),
    ("Рак лёгкого", "Pulmo", "neoplastic", 252),
    ("Ретинобластома", "Retinoblastoma", "neoplastic", 252),
    ("Опухоль пищевода", "Oesophagus", "neoplastic", 251),
    ("Опухоль поджелудочной железы", "Pancreas", "neoplastic", 251),
]


class PathomorphologicalExtractor(BaseExtractor):
    """Extract pathomorphological nosodes table (pages 246-252)."""

    def extract(self) -> dict:
        print("\n=== Extracting Pathomorphological Nosodes (pages 246-252) ===")

        records = []
        for condition_name, condition_name_lat, disease_category, source_page in PATHOMORPHOLOGICAL_DATA:
            records.append({
                "condition_name": condition_name,
                "condition_name_lat": condition_name_lat,
                "disease_category": disease_category,
                "source_page": source_page,
            })

        # Category stats
        cat_counts: dict[str, int] = {}
        for r in records:
            cat_counts[r["disease_category"]] = cat_counts.get(r["disease_category"], 0) + 1
        for cat, cnt in sorted(cat_counts.items()):
            print(f"  {cat}: {cnt}")

        print(f"  Total: {len(records)} conditions")

        self.save_debug("pathomorphological_nosodes", records)

        conn = self.get_db_connection()
        for rec in records:
            conn.execute(
                "INSERT INTO pathomorphological_nosodes "
                "(condition_name, condition_name_lat, disease_category, source_page) "
                "VALUES (?, ?, ?, ?)",
                (rec["condition_name"], rec["condition_name_lat"],
                 rec["disease_category"], rec["source_page"]),
            )
        conn.commit()

        print(f"  Inserted {len(records)} records into pathomorphological_nosodes")
        self.preview(conn, "pathomorphological_nosodes", 5)
        conn.close()

        return {"records": len(records)}
