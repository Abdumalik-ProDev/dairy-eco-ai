"""Multilingual localization (English, Uzbek, Russian) for the DairyEco AI Executive Platform."""

from __future__ import annotations

from typing import Any

from dairyeco.domain.models import DairyCategory, PackageFormat

LANGUAGES: dict[str, str] = {
    "en": "English",
    "uz": "Oʻzbekcha",
    "ru": "Русский",
}

CATEGORY_LABELS_I18N: dict[str, dict[DairyCategory, str]] = {
    "en": {
        DairyCategory.FLUID_MILK: "Fluid milk (pasteurized & UHT)",
        DairyCategory.YOGURT_KEFIR: "Yogurt, kefir & fermented dairy",
        DairyCategory.CHEESE: "Cheese (ripened, soft & fresh)",
        DairyCategory.BUTTER: "Butter & dairy spreads",
        DairyCategory.CREAM: "Cream & sour cream",
        DairyCategory.MILK_POWDER: "Milk powder & dry dairy",
        DairyCategory.ICE_CREAM: "Ice cream & frozen desserts",
        DairyCategory.OTHER_DAIRY: "Specialty dairy products",
    },
    "uz": {
        DairyCategory.FLUID_MILK: "Ichimlik suti (pasterizatsiyalangan va UHT)",
        DairyCategory.YOGURT_KEFIR: "Yogurt, kefir va qatiq mahsulotlari",
        DairyCategory.CHEESE: "Pishloq va tvorog mahsulotlari",
        DairyCategory.BUTTER: "Saryogʻ va sutli spredlar",
        DairyCategory.CREAM: "Qaymoq va smetana",
        DairyCategory.MILK_POWDER: "Quruq sut (sut kukuni)",
        DairyCategory.ICE_CREAM: "Muzqaymoq va muzlatilgan shirinliklar",
        DairyCategory.OTHER_DAIRY: "Maxsus sut mahsulotlari",
    },
    "ru": {
        DairyCategory.FLUID_MILK: "Питьевое молоко (пастеризованное и УВТ)",
        DairyCategory.YOGURT_KEFIR: "Йогурт, кефир и кисломолочные продукты",
        DairyCategory.CHEESE: "Сыры и творожные изделия",
        DairyCategory.BUTTER: "Сливочное масло и спреды",
        DairyCategory.CREAM: "Сливки и сметана",
        DairyCategory.MILK_POWDER: "Сухое молоко",
        DairyCategory.ICE_CREAM: "Мороженое и замороженные десерты",
        DairyCategory.OTHER_DAIRY: "Специальные молочные продукты",
    },
}

PACKAGE_FORMAT_I18N: dict[str, dict[PackageFormat, str]] = {
    "en": {
        PackageFormat.BOTTLE: "Bottle",
        PackageFormat.CARTON: "Composite Carton",
        PackageFormat.CUP: "Cup",
        PackageFormat.POUCH: "Flexible Pouch",
        PackageFormat.FILM_WRAP: "Foil / Film Wrap",
        PackageFormat.TUB: "Rigid Tray / Tub",
        PackageFormat.JAR: "Jar",
        PackageFormat.SACK: "Industrial Sack",
    },
    "uz": {
        PackageFormat.BOTTLE: "Butilka (shisha/plastik)",
        PackageFormat.CARTON: "Kompozit karton quti",
        PackageFormat.CUP: "Stakancha",
        PackageFormat.POUCH: "Yumshoq paket (pouch)",
        PackageFormat.FILM_WRAP: "Folga / plyonka oʻram",
        PackageFormat.TUB: "Qattiq lotok / konteyner",
        PackageFormat.JAR: "Banka",
        PackageFormat.SACK: "Sanoat qopi",
    },
    "ru": {
        PackageFormat.BOTTLE: "Бутылка",
        PackageFormat.CARTON: "Композитный картонный пакет",
        PackageFormat.CUP: "Стаканчик",
        PackageFormat.POUCH: "Мягкий пакет (дой-пак / подушка)",
        PackageFormat.FILM_WRAP: "Фольгированная / плёночная обёртка",
        PackageFormat.TUB: "Жёсткий лоток / контейнер",
        PackageFormat.JAR: "Банка",
        PackageFormat.SACK: "Промышленный мешок",
    },
}

PRESET_NAMES_I18N: dict[str, dict[str, tuple[str, str]]] = {
    "PKG-HDPE-BOTTLE-1L": {
        "en": (
            "1.0 kg Virgin HDPE Bottle",
            "Standard 1 kg HDPE dairy bottle with secondary corrugated tray/case.",
        ),
        "uz": (
            "1,0 kg birlamchi HDPE plastik butilka",
            "Standart 1 kg HDPE sut butilkasi va gofrokarton quti.",
        ),
        "ru": (
            "1,0 кг бутылка из первичного ПНД (HDPE)",
            "Стандартная молочная бутылка 1 кг из первичного ПНД в гофрокоробе.",
        ),
    },
    "PKG-PET-BOTTLE-1L": {
        "en": (
            "1.0 kg Virgin PET Bottle",
            "Standard 1 kg virgin PET dairy bottle.",
        ),
        "uz": (
            "1,0 kg birlamchi PET plastik butilka",
            "Standart 1 kg shaffof birlamchi PET sut butilkasi.",
        ),
        "ru": (
            "1,0 кг бутылка из первичного ПЭТ (PET)",
            "Стандартная молочная бутылка 1 кг из первичного прозрачного ПЭТ.",
        ),
    },
    "PKG-RPET50-BOTTLE-1L": {
        "en": (
            "1.0 kg Lightweight 50% rPET Bottle",
            "Lightweight PET bottle with 50% food-grade recycled PET (rPET) and 85%-recycled corrugated case.",
        ),
        "uz": (
            "1,0 kg yengillashtirilgan 50% ikkilamchi rPET butilka",
            "50% oziq-ovqat uchun yaroqli qayta ishlangan rPET va 85% ikkilamchi gofrokartondan tayyorlangan yengil butilka.",
        ),
        "ru": (
            "1,0 кг облегчённая бутылка с 50% вторичного ПЭТ (rPET)",
            "Облегчённая ПЭТ-бутылка с 50% пищевого rPET и гофрокоробом из 85% макулатуры.",
        ),
    },
    "PKG-CARTON-LPB-1L": {
        "en": (
            "1.0 kg Composite Aseptic Carton (LPB + LDPE + Al Foil)",
            "Multilayer composite aseptic carton (71% board, 16.5% LDPE, 4.8% Al foil, 7.9% HDPE cap).",
        ),
        "uz": (
            "1,0 kg koʻp qatlamli aseptik karton (LPB + LDPE + alyuminiy folga)",
            "Koʻp qatlamli aseptik karton qadoq (71% karton, 16,5% LDPE, 4,8% alyuminiy folga, 7,9% HDPE qopqoq).",
        ),
        "ru": (
            "1,0 кг композитный асептический картонный пакет (картон + ПЭВД + фольга)",
            "Многослойный асептический пакет (71% картон, 16,5% ПЭВД, 4,8% алюминиевая фольга, 7,9% крышка ПНД).",
        ),
    },
    "PKG-GLASS-SINGLE-1L": {
        "en": (
            "1.0 kg Single-Use Glass Bottle (35% Cullet)",
            "Single-use glass bottle; illustrates high mass and energy penalty without reuse.",
        ),
        "uz": (
            "1,0 kg bir martalik shisha butilka (35% ikkilamchi shisha)",
            "Bir martalik shisha butilka; qayta ishlatilmasa yuqori vazn va energiya sarfini keltirib chiqaradi.",
        ),
        "ru": (
            "1,0 кг одноразовая стеклянная бутылка (35% стеклобоя)",
            "Одноразовая стеклянная бутылка; высокая масса и энергоёмкость при отсутствии возвратного оборота.",
        ),
    },
    "PKG-GLASS-REUSE-1L": {
        "en": (
            "1.0 kg Returnable Glass Bottle (20 Max Trips, 90% Return)",
            "Returnable glass bottle with caustic washing and reverse transport loop.",
        ),
        "uz": (
            "1,0 kg koʻp martalik qaytariladigan shisha butilka (20 marta aylanish, 90% qaytish)",
            "Yuvish va qayta yigʻish tizimiga ega koʻp martalik aylanma shisha butilka.",
        ),
        "ru": (
            "1,0 кг возвратная стеклянная бутылка (до 20 циклов, 90% возврат)",
            "Многооборотная стеклянная бутылка с циклом мойки и обратной логистикой.",
        ),
    },
    "PKG-POUCH-LDPE-1L": {
        "en": (
            "1.0 kg Flexible LDPE/LLDPE Pillow Pouch",
            "Ultra-lightweight flexible PE pouch; very low resin cost/mass but higher product spoilage/puncture loss (1.8%).",
        ),
        "uz": (
            "1,0 kg yumshoq polietilen paket (LDPE/LLDPE)",
            "Oʻta yengil polietilen paket; plastik sarfi juda kam, ammo mahsulot yoʻqotilishi (1,8%) yuqoriroq.",
        ),
        "ru": (
            "1,0 кг мягкий полиэтиленовый пакет-подушка (ПЭВД/ЛПЭНП)",
            "Сверхлёгкий полиэтиленовый пакет; минимальный расход сырья, но повышенные потери продукта при проколах (1,8%).",
        ),
    },
    "PKG-PP-CUP-400G": {
        "en": (
            "400 g Thermoformed Virgin PP Cup + Al Foil Lid",
            "Standard 400 g thermoformed PP dairy cup with aluminium heat-seal lid.",
        ),
        "uz": (
            "400 g birlamchi PP plastik stakancha + alyuminiy folga qopqoq",
            "Standart 400 g polipropilen (PP) stakancha va kavsharlanadigan alyuminiy folga qopqoq.",
        ),
        "ru": (
            "400 г термоформованный стаканчик из первичного ПП + фольгированная крышка",
            "Стандартный полипропиленовый стаканчик 400 г с термоспаиваемой алюминиевой платинкой.",
        ),
    },
    "PKG-RPP30-CUP-400G": {
        "en": (
            "400 g Lightweight K3-Style 30% rPP Cup + Recycled Board Wrap",
            "Lightweight PP inner cup reinforced by tear-off recycled paperboard wrap.",
        ),
        "uz": (
            "400 g yengillashtirilgan K3-uslubidagi 30% rPP stakancha + karton belbogʻ",
            "Ajratib olinadigan ikkilamchi karton qobiq bilan mustahkamlangan yengil 30% rPP stakancha.",
        ),
        "ru": (
            "400 г облегчённый стаканчик K3 (30% rPP) с картонным манжетом",
            "Облегчённый стаканчик с 30% вторичного ПП, усиленный съёмной обечайкой из переработанного картона.",
        ),
    },
    "PKG-CHEESE-FLOWPACK-250G": {
        "en": (
            "250 g Cheese Rigid PET Tray + Barrier Film Flowpack",
            "250 g ripened cheese MAP thermoformed tray + barrier film.",
        ),
        "uz": (
            "250 g pishloq uchun qattiq PET lotok + baryer plyonka (Flowpack)",
            "250 g pishloq uchun gaz muhitida (MAP) qadoqlangan qattiq PET lotok va himoya plyonkasi.",
        ),
        "ru": (
            "250 г жёсткий ПЭТ-лоток для сыра + барьерная плёнка флоу-пак",
            "Термоформованный лоток 250 г с газомодифицированной средой (МГС) и барьерной плёнкой.",
        ),
    },
    "PKG-BUTTER-FOILWRAP-200G": {
        "en": (
            "200 g Butter Aluminium-Parchment Laminate Wrap",
            "Traditional 200 g butter foil-parchment wrap.",
        ),
        "uz": (
            "200 g saryogʻ uchun alyuminiy-pergament laminat oʻram",
            "Anʼanaviy 200 g saryogʻ uchun folga va pergament qogʻozli oʻram.",
        ),
        "ru": (
            "200 г кашированная фольга с пергаментом для сливочного масла",
            "Традиционная обёртка 200 г из алюминиевой фольги и пергаментной бумаги.",
        ),
    },
    "PKG-POWDER-SACK-25KG": {
        "en": (
            "25 kg Milk Powder Multi-wall Kraft Sack with LDPE Liner",
            "25 kg industrial bulk milk powder multi-wall paper sack with inner PE liner.",
        ),
        "uz": (
            "25 kg quruq sut uchun koʻp qavatli kraft-qogʻoz qop (LDPE vkladish bilan)",
            "Ichki polietilen himoya qatlamiga ega 25 kg sanoat kraft-qogʻoz qopi.",
        ),
        "ru": (
            "25 кг многослойный крафт-мешок для сухого молока с ПЭ-вкладышем",
            "Промышленный бумажный мешок 25 кг с внутренним влагозащитным полиэтиленовым вкладышем.",
        ),
    },
}

SENSITIVITY_LABELS_I18N: dict[str, dict[str, str]] = {
    "package_component_unit_price": {
        "en": "Packaging material unit price (±20%)",
        "uz": "Qadoqlash xomashyosi narxi (±20%)",
        "ru": "Цена упаковочного сырья (±20%)",
    },
    "package_component_mass": {
        "en": "Package weight / wall thickness (±20%)",
        "uz": "Qadoq vazni / devor qalinligi (±20%)",
        "ru": "Масса упаковки / толщина стенок (±20%)",
    },
    "grid_carbon_intensity": {
        "en": "Electricity grid carbon intensity (±20%)",
        "uz": "Elektr tarmogʻi uglerod sigʻimi (±20%)",
        "ru": "Углеродоёмкость электросети (±20%)",
    },
    "spoilage_loss_rate": {
        "en": "Package-related product spoilage rate (±20%)",
        "uz": "Qadoq sababli mahsulot nobudgarchiligi (±20%)",
        "ru": "Доля потерь и порчи продукта из-за упаковки (±20%)",
    },
    "transport_distance": {
        "en": "Supply & distribution distance (±20%)",
        "uz": "Yetkazib berish va logistika masofasi (±20%)",
        "ru": "Расстояние поставок и дистрибуции (±20%)",
    },
    "electricity_price": {
        "en": "Electricity tariff (±20%)",
        "uz": "Elektr energiyasi tarifi (±20%)",
        "ru": "Тариф на электроэнергию (±20%)",
    },
    "reuse_return_rate": {
        "en": "Returnable bottle return rate (80%–98%)",
        "uz": "Koʻp martalik shisha qaytish darajasi (80%–98%)",
        "ru": "Доля возврата оборотной бутылки (80%–98%)",
    },
}

EXACT_PRODUCT_TRANSLATIONS: dict[str, tuple[str, str]] = {
    "Milk, semi-skimmed, pasteurised": (
        "Pasterizatsiyalangan yarim yogʻsizlantirilgan sut (1,5–2,5%)",
        "Молоко пастеризованное полуобезжиренное (1,5–2,5%)",
    ),
    "Milk, semi-skimmed, UHT": (
        "UHT (ultrapasterizatsiyalangan) yarim yogʻsizlantirilgan sut",
        "Молоко ультрапастеризованное (УВТ) полуобезжиренное",
    ),
    "Milk, whole, pasteurised": (
        "Pasterizatsiyalangan tabiiy yogʻli sut (3,2–3,5%)",
        "Молоко пастеризованное цельное (3,2–3,5%)",
    ),
    "Milk, whole, UHT": (
        "UHT (ultrapasterizatsiyalangan) tabiiy yogʻli sut",
        "Молоко ультрапастеризованное (УВТ) цельное",
    ),
    "Milk, skimmed, pasteurised": (
        "Pasterizatsiyalangan yogʻsizlantirilgan sut",
        "Молоко пастеризованное обезжиренное",
    ),
    "Milk, skimmed, UHT": (
        "UHT yogʻsizlantirilgan sut",
        "Молоко ультрапастеризованное (УВТ) обезжиренное",
    ),
    "Milk, semi-skimmed, reduced lactose": (
        "Laktozasi kamaytirilgan yarim yogʻsizlantirilgan sut",
        "Молоко низколактозное полуобезжиренное",
    ),
    "Milk, semi-skimmed, vitamin D fortified, UHT": (
        "D vitamini bilan boyitilgan UHT yarim yogʻsizlantirilgan sut",
        "Молоко УВТ полуобезжиренное, обогащённое витамином D",
    ),
    "Condensed milk, without sugar, whole": (
        "Shakarsiz quyultirilgan tabiiy sut",
        "Молоко сгущённое без сахара цельное",
    ),
    "Condensed milk, with sugar, whole": (
        "Shakarli quyultirilgan tabiiy sut (sgushonka)",
        "Молоко цельное сгущённое с сахаром",
    ),
    "Goat milk, half skimmed, UHT pasteurized": (
        "Echki suti, yarim yogʻsizlantirilgan, UHT",
        "Козье молоко полуобезжиренное УВТ",
    ),
    "Goat milk, whole, raw": (
        "Tabiiy xom echki suti",
        "Козье молоко цельное сырое",
    ),
    "Goat milk, whole, UHT": (
        "UHT tabiiy echki suti",
        "Козье молоко цельное УВТ",
    ),
    "Sheep milk, whole": (
        "Tabiiy qoʻy suti",
        "Овечье молоко цельное",
    ),
    "Milk, powder, semi-skimmed, non rehydrated": (
        "Quruq sut (yarim yogʻsizlantirilgan sut kukuni)",
        "Сухое полуобезжиренное молоко",
    ),
    "Milk, powder, skimmed, non rehydrated": (
        "Yogʻsizlantirilgan quruq sut (SOM)",
        "Сухое обезжиренное молоко (СОМ)",
    ),
    "Milk, powder, whole, non rehydrated": (
        "Yogʻli quruq sut (SMM)",
        "Сухое цельное молоко (СЦМ)",
    ),
    "Butter, 82% fat, unsalted": (
        "Tuzsiz saryogʻ, 82% yogʻlilikda",
        "Масло сливочное несолёное, 82% жирности",
    ),
    "Butter, 80% fat, salted": (
        "Tuzli saryogʻ, 80% yogʻlilikda",
        "Масло сливочное солёное, 80% жирности",
    ),
    "Butter, 80% fat, lightly salted": (
        "Kam tuzlangan saryogʻ, 80% yogʻlilikda",
        "Масло сливочное слабосолёное, 80% жирности",
    ),
    "Thick cream 30% fat, refrigerated": (
        "Quyuq qaymoq / smetana 30% yogʻli (sovutilgan)",
        "Густые сливки / сметана 30% жирности (охлаждённые)",
    ),
    "Liquid cream 30% fat, UHT": (
        "Suyuq qaymoq 30% yogʻli (UHT)",
        "Сливки питьевые 30% жирности (УВТ)",
    ),
    "Dairy drink or fermented milk or yogurt, plain, with sugar, with L Casei": (
        "Tabiiy ichimlik yogurti / kefir (shakarli, L. Casei bilan)",
        "Кисломолочный напиток / питьевой йогурт с сахаром и L. Casei",
    ),
    "Dairy drink or fermented milk or yogurt, with fruits, with sugar": (
        "Mevali ichimlik yogurti / kefir (shakarli)",
        "Фруктовый питьевой йогурт / кисломолочный напиток с сахаром",
    ),
    "Dairy drink or fermented milk or yogurt, flavoured, with sugar": (
        "Xushboʻylashtirilgan ichimlik yogurti / kefir",
        "Ароматизированный питьевой йогурт / кисломолочный напиток",
    ),
}


def localize_product_name(name_en: str, lang: str) -> str:
    """Return localized dairy product name in English, Uzbek, or Russian."""
    if lang == "en":
        return name_en
    if name_en in EXACT_PRODUCT_TRANSLATIONS:
        uz_name, ru_name = EXACT_PRODUCT_TRANSLATIONS[name_en]
        return uz_name if lang == "uz" else ru_name

    text = name_en
    if lang == "uz":
        replacements = [
            ("from cow's milk", "sigir sutidan"),
            ("from goat's milk", "echki sutidan"),
            ("from sheep's milk", "qoʻy sutidan"),
            ("Dairy drink or fermented milk or yogurt", "Yogurt yoki achitilgan sut ichimligi"),
            ("Thick cream", "Quyuq qaymoq (smetana)"),
            ("Liquid cream", "Suyuq qaymoq"),
            ("Whipped cream", "Koʻpirtirilgan qaymoq"),
            ("Fresh cheese", "Yangi pishloq (tvorog)"),
            ("Soft cheese", "Yumshoq pishloq"),
            ("Processed cheese", "Eritilgan pishloq"),
            ("cheese", "pishloq"),
            ("Cheese", "Pishloq"),
            ("Butter", "Saryogʻ"),
            ("Yogurt", "Yogurt"),
            ("yogurt", "yogurt"),
            ("Ice cream", "Muzqaymoq"),
            ("ice cream", "muzqaymoq"),
            ("semi-skimmed", "yarim yogʻsizlantirilgan"),
            ("skimmed", "yogʻsizlantirilgan"),
            ("whole", "tabiiy yogʻli"),
            ("pasteurised", "pasterizatsiyalangan"),
            ("refrigerated", "sovutilgan"),
            ("unsalted", "tuzsiz"),
            ("lightly salted", "kam tuzlangan"),
            ("salted", "tuzli"),
            ("with fruits", "mevali"),
            ("with sugar", "shakarli"),
            ("without sugar", "shakarsiz"),
            ("plain", "oddiy"),
            ("fat", "yogʻli"),
        ]
    else:
        replacements = [
            ("from cow's milk", "из коровьего молока"),
            ("from goat's milk", "из козьего молока"),
            ("from sheep's milk", "из овечьего молока"),
            ("Dairy drink or fermented milk or yogurt", "Кисломолочный напиток или йогурт"),
            ("Thick cream", "Густые сливки / сметана"),
            ("Liquid cream", "Питьевые сливки"),
            ("Whipped cream", "Взбитые сливки"),
            ("Fresh cheese", "Свежий творожный сыр"),
            ("Soft cheese", "Мягкий сыр"),
            ("Processed cheese", "Плавленый сыр"),
            ("cheese", "сыр"),
            ("Cheese", "Сыр"),
            ("Butter", "Масло сливочное"),
            ("Yogurt", "Йогурт"),
            ("yogurt", "йогурт"),
            ("Ice cream", "Мороженое"),
            ("ice cream", "мороженое"),
            ("semi-skimmed", "полуобезжиренное"),
            ("skimmed", "обезжиренное"),
            ("whole", "цельное"),
            ("pasteurised", "пастеризованное"),
            ("refrigerated", "охлаждённое"),
            ("unsalted", "несолёное"),
            ("lightly salted", "слабосолёное"),
            ("salted", "солёное"),
            ("with fruits", "с фруктами"),
            ("with sugar", "с сахаром"),
            ("without sugar", "без сахара"),
            ("plain", "классический"),
            ("fat", "жирности"),
        ]
    for src, dst in replacements:
        text = text.replace(src, dst)
    return text


def localize_preset_name(config_id: str, fallback_name: str, lang: str) -> str:
    if config_id in PRESET_NAMES_I18N and lang in PRESET_NAMES_I18N[config_id]:
        return PRESET_NAMES_I18N[config_id][lang][0]
    return fallback_name


def localize_preset_notes(config_id: str, fallback_notes: str, lang: str) -> str:
    if config_id in PRESET_NAMES_I18N and lang in PRESET_NAMES_I18N[config_id]:
        return PRESET_NAMES_I18N[config_id][lang][1]
    return fallback_notes


def localize_sensitivity_label(param_key: str, fallback_label: str, lang: str) -> str:
    if param_key in SENSITIVITY_LABELS_I18N and lang in SENSITIVITY_LABELS_I18N[param_key]:
        return SENSITIVITY_LABELS_I18N[param_key][lang]
    return fallback_label


UI_TEXT: dict[str, dict[str, Any]] = {
    "en": {
        "language_label": "Platform language",
        "brand_subtitle": "DairyEco AI — Executive Decision Platform",
        "main_title": "What happens if we switch our dairy packaging?",
        "main_caption": (
            "Compare the business and environmental impact of switching from your current packaging "
            "to an alternative format — powered by verified LCA data (`AGRIBALYSE 3.2`, `NIST 2024`, `USLCI`, `IFC 2007`)."
        ),
        "sec1_title": "1. Build your packaging transition scenario",
        "lbl_category": "Dairy product category",
        "lbl_product": "Specific dairy product",
        "lbl_volume": "Annual production volume (tonnes / year)",
        "hlp_volume": "1 tonne = 1,000 kg of saleable dairy product delivered to customers.",
        "lbl_current_pkg": "Current packaging (baseline)",
        "lbl_proposed_pkg": "Proposed alternative packaging",
        "lbl_check_compat": " [Check compatibility]",
        "lbl_period": "Comparison period",
        "fmt_years": lambda y: f"{y} year{'s' if y > 1 else ''}",
        "exp_assumptions": "Customize financial, equipment & regional assumptions",
        "lbl_capex": "Equipment investment / CAPEX ($)",
        "hlp_capex": "Upfront packaging line modification or new equipment purchase cost.",
        "lbl_install": "Installation & commissioning ($)",
        "lbl_selling_price": "Product net selling price ($ / kg)",
        "hlp_selling_price": "Used to calculate annual revenue and contribution margin.",
        "lbl_spoilage_cost": "Spoiled product cost ($ / kg lost)",
        "hlp_spoilage_cost": "Production cost of dairy product lost to package breakage or spoilage.",
        "lbl_resin_region": "Polymer supply region (NIST 2024)",
        "lbl_grid": "Electricity grid carbon intensity",
        "lbl_discount": "Annual discount rate for NPV (%)",
        "lbl_return_rate": "Returnable bottle return rate (%)",
        "hlp_return_rate": "Applies when evaluating reusable glass bottle configurations.",
        # Decision classifications
        "verdict_infeasible": "Technically incompatible with selected dairy product",
        "badge_infeasible": "Incompatible format",
        "verdict_win_win": "Both economically and environmentally beneficial (Win-Win)",
        "badge_win_win": "Recommended: Win-Win transition",
        "verdict_env_only": "Environmentally beneficial, with a net financial cost",
        "badge_env_only": "Sustainability investment (cuts emissions, higher cost)",
        "verdict_econ_only": "Economically beneficial, but increases environmental footprint",
        "badge_econ_only": "Cost-saving trade-off (saves money, higher emissions)",
        "verdict_neither": "Neither economically nor environmentally beneficial",
        "badge_neither": "Not recommended (higher cost & higher emissions)",
        "verdict_baseline": "Current baseline",
        "cum_box_caption": lambda yrs: f"Cumulative {yrs}-year financial & carbon impact",
        "cum_net_cash": lambda yrs, val: f"- **{yrs}-year net cash impact (incl. CAPEX):** **{val}**",
        "cum_co2": lambda yrs, val: f"- **{yrs}-year cumulative CO₂e change:** **{val:+.1f} tonnes CO₂e**",
        "cum_plastic": lambda yrs, val: f"- **{yrs}-year virgin plastic change:** **{val:+.1f} tonnes**",
        "err_infeasible_title": "Technical compatibility violation",
        "warn_operational_title": "Operational note",
        # Section 2: Business impact
        "sec2_title": "2. Business & financial impact",
        "sec2_caption": lambda tonnes, yrs, inv, disc: (
            f"Scenario economics for **{tonnes:,} tonnes/year** over a **{yrs}-year** horizon "
            f"(upfront CAPEX + installation: **{inv}**; discount rate: **{disc:.1f}%**)."
        ),
        "m_prop_cost": "Proposed annual packaging cost",
        "m_prop_cost_delta": lambda pct, base_val: f"{pct} vs. {base_val}",
        "m_prop_cost_help": "Includes packaging materials, inbound/outbound freight, reuse washing, waste disposal, and package-attributable dairy spoilage.",
        "m_savings_pos": "Annual cost savings",
        "m_savings_neg": "Additional annual expense",
        "m_savings_val": lambda val: f"{val} / yr",
        "m_savings_delta": lambda val, yrs: f"{val} over {yrs} yrs",
        "m_savings_help": "Annual operating cash flow difference (Current cost minus Proposed cost).",
        "m_payback": "Payback period",
        "m_payback_yrs": lambda y: f"{y:.1f} years",
        "m_payback_within": "Pays back within horizon",
        "m_payback_exceeds": lambda yrs: f"Exceeds {yrs}-yr horizon",
        "m_payback_immediate": "Immediate (0 yrs)",
        "m_payback_no_capex": "No upfront CAPEX required",
        "m_payback_none": "No payback",
        "m_payback_cost_up": "Operating cost increases",
        "m_payback_help": lambda inv: f"Upfront investment of {inv} divided by annual cash savings.",
        "m_npv": lambda yrs: f"{yrs}-year Net Present Value",
        "m_be_vol": lambda t: f"Break-even: {t:,.0f} t/yr",
        "m_be_none": "No volume break-even",
        "m_npv_help": "Discounted cash flow value of switching after accounting for upfront CAPEX.",
        "m_margin": "Annual contribution margin",
        "m_margin_delta": lambda val: f"{val} / yr margin impact",
        "m_margin_help": "Estimated annual revenue minus total packaging and plant operating costs.",
        # Section 3: Environmental impact
        "sec3_title": "3. Environmental impact",
        "sec3_caption": "Annual environmental footprint of packaging manufacture, converting, transport, washing, end-of-life, and package-related product spoilage.",
        "m_co2": "Packaging carbon footprint",
        "m_co2_val": lambda v: f"{v:,.1f} t CO₂e/yr",
        "m_co2_delta": lambda d, pct: f"{d:+,.1f} t ({pct})",
        "m_co2_help": lambda pct: f"Whole-product lifecycle change (including raw milk & dairy processing): {pct}.",
        "m_plastic": "Virgin fossil plastic use",
        "m_plastic_val": lambda v: f"{v:,.1f} t/yr",
        "m_plastic_delta": lambda d, pct: f"{d:+,.1f} t ({pct})",
        "m_plastic_help": "Annual mass of virgin fossil polymer resin consumed (excludes recycled content and bio-based polymers).",
        "m_waste": "Landfill & incinerated waste",
        "m_waste_val": lambda v: f"{v:,.1f} t/yr",
        "m_waste_delta": lambda d, pct: f"{d:+,.1f} t ({pct})",
        "m_waste_help": lambda rec: f"Packaging waste sent to landfill or incineration. Recycled packaging mass: {rec:,.1f} t/yr.",
        "m_water": "Water consumption",
        "m_water_val": lambda v: f"{v:,.0f} m³/yr",
        "m_water_delta": lambda d, pct: f"{d:+,.0f} m³ ({pct})",
        "m_water_help": "Packaging material production water plus bottle washing water for reusable containers.",
        "m_energy": "Packaging energy demand",
        "m_energy_val": lambda v: f"{v:,.0f} GJ/yr",
        "m_energy_delta": lambda d, pct: f"{d:+,.0f} GJ ({pct})",
        "m_energy_help": "Fossil and electrical energy consumed across packaging production, converting, and washing.",
        # Section 4: Visual comparison
        "sec4_title": "4. Side-by-side comparison: Current vs. Proposed",
        "badge_current_card": "Current packaging (Baseline)",
        "badge_proposed_card": "Proposed packaging (Alternative)",
        "lbl_cost_per_pkg": "Cost per package",
        "lbl_co2_per_pkg": "Carbon per package",
        "lbl_pkg_weight": "Package weight",
        "reusable_yes": lambda trips: f"Reusable ({trips:.1f} effective trips)",
        "reusable_no": "Single-use",
        "card_bullets": lambda mat, fmt, rec, eol, spoil_pct, spoil_t: (
            f"- **Primary material:** {mat} ({fmt})\n"
            f"- **Recycled content:** {rec} | **End-of-life recycling:** {eol}\n"
            f"- **Product spoilage rate:** {spoil_pct} ({spoil_t:,.1f} tonnes/yr lost)"
        ),
        "chart_cost_title": "Annual packaging cost breakdown ($ / year)",
        "chart_cost_x": "Annual cost ($ / year)",
        "chart_co2_title": "Annual carbon emissions by lifecycle stage (tonnes CO₂e / year)",
        "chart_co2_x": "Annual emissions (tonnes CO₂e / year)",
        "scen_current": "Current packaging",
        "scen_proposed": "Proposed packaging",
        "scen_alt": "Alternative",
        "cost_drivers": {
            "raw": "Raw materials & closures",
            "spoilage": "Product spoilage & fill loss",
            "freight": "Freight & distribution",
            "washing": "Reuse washing loop",
            "waste": "Waste disposal (net of scrap credit)",
        },
        "co2_stages": {
            "raw": "Raw material (resin, board, glass)",
            "converting": "Package converting & molding",
            "spoilage": "Product spoilage carbon loss",
            "transport": "Transport & reverse logistics",
            "washing_eol": "Reuse washing & end-of-life",
        },
        # Expanders
        "exp_all_options": "Compare all compatible packaging alternatives for this product",
        "exp_all_caption": "See how every compatible packaging format compares against your current packaging on annual cost and carbon footprint.",
        "col_option": "Packaging option",
        "col_selection": "Selection",
        "col_ann_cost": "Annual packaging cost ($/yr)",
        "col_cost_diff": "Annual cost change ($/yr)",
        "col_co2": "Packaging CO₂e (t/yr)",
        "col_co2_pct": "CO₂e change (%)",
        "col_plastic": "Virgin plastic (t/yr)",
        "col_payback": "Payback (yrs)",
        "col_decision": "Decision summary",
        "exp_provenance": "Data sources, uncertainty & sensitivity analysis",
        "sens_title": "What could change these results? (±20% parameter sensitivity)",
        "sens_caption": lambda pkg_name, tonnes: (
            f"Impact of ±20% market or operational swings on **{pkg_name}** (scaled to **{tonnes:,} tonnes/year**)."
        ),
        "col_sens_param": "Key assumption",
        "col_sens_cost": "Annual cost swing ($/yr)",
        "col_sens_co2": "Annual CO₂e swing (t/yr)",
        "prov_title": "Published data vs. scenario assumptions",
        "prov_alert_title": "Data provenance & limitations",
        "prov_body": (
            "- **Published LCA reference data (`published_reference`):**\n"
            "  - **AGRIBALYSE 3.2 (ADEME / INRAE):** De-packaged dairy product footprints "
            "(baseline `Emballage` subtracted so packaging is never double-counted).\n"
            "  - **NIST / Argonne GREET 2024:** Regionalized virgin & recycled polymer resin footprints.\n"
            "  - **USLCI (NREL) & Literature Proxies:** Paperboard, glass, aluminium, converting, and freight.\n"
            "  - **IFC / World Bank (2007):** Dairy processing energy, water, and packaging mass benchmarks.\n"
            "- **Scenario assumptions (`assumed` / `proxy`):**\n"
            "  - Unit resin/board prices, CAPEX, utility tariffs, and spoilage costs are editable scenario assumptions "
            "and should be calibrated with your supplier quotes before final capital commitment."
        ),
        "btn_download": "Download full scenario report (.md)",
        "lbl_dev_mode": "Developer Mode",
        "lbl_mat_price_adj": "Proposed packaging material price adjustment (%)",
        "m_capex": "Initial investment (CAPEX)",
        "m_capex_delta": lambda eq, inst: f"Equip {eq} + Install {inst}",
        "m_inc_cf": "Annual incremental net cash flow",
        "m_payback_yrs_mos": lambda y, m: f"{y:.2f} yrs ({m:.1f} mos)",
        "m_cum_cf": lambda yrs: f"{yrs}-year cumulative net cash flow",
        "exp_cf_schedule": "View year-by-year cumulative cash flow & payback schedule",
    },
    "uz": {
        "language_label": "Platforma tili",
        "brand_subtitle": "DairyEco AI — Rahbarlar uchun qaror qabul qilish platformasi",
        "main_title": "Sut mahsulotlari qadoqlarini oʻzgartirsak nima boʻladi?",
        "main_caption": (
            "Joriy qadoqlash turidan ekologik muqobil variantga oʻtishning biznes va atrof-muhitga taʼsirini solishtiring — "
            "xalqaro LCA maʼlumotlar bazalari (`AGRIBALYSE 3.2`, `NIST 2024`, `USLCI`, `IFC 2007`) asosida."
        ),
        "sec1_title": "1. Qadoqlashni yangilash ssenariysini tanlang",
        "lbl_category": "Sut mahsuloti toifasi",
        "lbl_product": "Aniq sut mahsuloti",
        "lbl_volume": "Yillik ishlab chiqarish hajmi (tonna / yil)",
        "hlp_volume": "1 tonna = xaridorga yetkazib beriladigan 1 000 kg tayyor sut mahsuloti.",
        "lbl_current_pkg": "Joriy qadoqlash (bazaviy variant)",
        "lbl_proposed_pkg": "Taklif etilayotgan muqobil qadoqlash",
        "lbl_check_compat": " [Moslikni tekshiring]",
        "lbl_period": "Taqqoslash davri",
        "fmt_years": lambda y: f"{y} yil",
        "exp_assumptions": "Moliyaviy, uskuna (CAPEX) va mintaqaviy koʻrsatkichlarni sozlash",
        "lbl_capex": "Uskunalar uchun investitsiya / CAPEX ($)",
        "hlp_capex": "Qadoqlash liniyasini qayta jihozlash yoki yangi uskuna xarid qilish qiymati.",
        "lbl_install": "Oʻrnatish va ishga tushirish xarajati ($)",
        "lbl_selling_price": "Mahsulotning sof sotish narxi ($ / kg)",
        "hlp_selling_price": "Yillik tushum va marjani hisoblash uchun ishlatiladi.",
        "lbl_spoilage_cost": "Yaroqsiz boʻlgan mahsulot tannarxi ($ / kg)",
        "hlp_spoilage_cost": "Qadoq shikastlanishi yoki buzilishi tufayli yoʻqotilgan sut mahsuloti qiymati.",
        "lbl_resin_region": "Polimer xomashyosi mintaqasi (NIST 2024)",
        "lbl_grid": "Elektr tarmogʻining uglerod sigʻimi",
        "lbl_discount": "NPV uchun yillik diskont stavkasi (%)",
        "lbl_return_rate": "Koʻp martalik shisha butilkalarning qaytish darajasi (%)",
        "hlp_return_rate": "Koʻp martalik shisha butilka tanlanganda qoʻllaniladi.",
        # Decision classifications
        "verdict_infeasible": "Tanlangan sut mahsuloti uchun texnik jihatdan mos emas",
        "badge_infeasible": "Texnik mos kelmaydi",
        "verdict_win_win": "Ham iqtisodiy, ham ekologik jihatdan foydali (Ikki tomonlama yutuq)",
        "badge_win_win": "Tavsiya etiladi: Iqtisodiy va ekologik foydali",
        "verdict_env_only": "Ekologik jihatdan foydali, ammo qoʻshimcha xarajat talab qiladi",
        "badge_env_only": "Ekologik investitsiya (zararni kamaytiradi, xarajat oshadi)",
        "verdict_econ_only": "Iqtisodiy jihatdan tejamkor, ammo ekologik yuklamani oshiradi",
        "badge_econ_only": "Moliyaviy tejamkor (xarajat kamayadi, emissiya oshadi)",
        "verdict_neither": "Na iqtisodiy, na ekologik jihatdan foydali",
        "badge_neither": "Tavsiya etilmaydi (xarajat ham, ekologik zarar ham oshadi)",
        "verdict_baseline": "Joriy bazaviy qadoq",
        "cum_box_caption": lambda yrs: f"{yrs} yillik jami moliyaviy va ekologik natija",
        "cum_net_cash": lambda yrs, val: f"- **{yrs} yillik sof pul oqimi (CAPEX bilan):** **{val}**",
        "cum_co2": lambda yrs, val: f"- **{yrs} yillik jami CO₂e oʻzgarishi:** **{val:+.1f} tonna CO₂e**",
        "cum_plastic": lambda yrs, val: f"- **{yrs} yillik birlamchi plastik oʻzgarishi:** **{val:+.1f} tonna**",
        "err_infeasible_title": "Texnik moslik talabi buzilgan",
        "warn_operational_title": "Ishlab chiqarish boʻyicha eslatma",
        # Section 2: Business impact
        "sec2_title": "2. Biznes va moliyaviy koʻrsatkichlar",
        "sec2_caption": lambda tonnes, yrs, inv, disc: (
            f"Yiliga **{tonnes:,} tonna** ishlab chiqarish hajmi va **{yrs} yillik** davr uchun iqtisodiy tahlil "
            f"(boshlangʻich CAPEX va oʻrnatish: **{inv}**; diskont stavkasi: **{disc:.1f}%**)."
        ),
        "m_prop_cost": "Taklif etilayotgan yillik qadoqlash xarajati",
        "m_prop_cost_delta": lambda pct, base_val: f"{pct} (joriy: {base_val})",
        "m_prop_cost_help": "Qadoqlash materiallari, logistika, yuvish, chiqindilarni utilizatsiya qilish va qadoq sababli mahsulot yoʻqotilishini oʻz ichiga oladi.",
        "m_savings_pos": "Yillik tejamkorlik (foyda)",
        "m_savings_neg": "Qoʻshimcha yillik xarajat",
        "m_savings_val": lambda val: f"{val} / yil",
        "m_savings_delta": lambda val, yrs: f"{yrs} yilda jami {val}",
        "m_savings_help": "Joriy va taklif etilayotgan yillik qadoqlash xarajatlari oʻrtasidagi farq.",
        "m_payback": "Oʻzini oqlash muddati (Payback)",
        "m_payback_yrs": lambda y: f"{y:.1f} yil",
        "m_payback_within": "Tanlangan davr ichida qoplanadi",
        "m_payback_exceeds": lambda yrs: f"{yrs} yillik davrdan oshadi",
        "m_payback_immediate": "Darhol (0 yil)",
        "m_payback_no_capex": "Boshlangʻich CAPEX talab etilmaydi",
        "m_payback_none": "Oʻzini qoplamaydi",
        "m_payback_cost_up": "Joriy xarajatlar oshadi",
        "m_payback_help": lambda inv: f"{inv} boshlangʻich investitsiyaning yillik tejamkorlik hisobiga qoplanish muddati.",
        "m_npv": lambda yrs: f"{yrs} yillik sof joriy qiymat (NPV)",
        "m_be_vol": lambda t: f"Zararsizlik nuqtasi: {t:,.0f} t/yil",
        "m_be_none": "Hajm boʻyicha zararsizlik nuqtasi yoʻq",
        "m_npv_help": "Boshlangʻich CAPEX hisobga olingan holda diskontlangan pul oqimi qiymati.",
        "m_margin": "Yillik marjinal daromad",
        "m_margin_delta": lambda val: f"Yillik marja oʻzgarishi: {val}",
        "m_margin_help": "Yillik tushumdan qadoqlash va zavod operatsion xarajatlari chegirilgandagi qoldiq.",
        # Section 3: Environmental impact
        "sec3_title": "3. Atrof-muhitga (ekologik) taʼsir",
        "sec3_caption": "Qadoq xomashyosini olish, ishlab chiqarish, tashish, yuvish, chiqindi va mahsulot nobudgarchiligining yillik ekologik izi.",
        "m_co2": "Qadoqlashning uglerod izi (CO₂e)",
        "m_co2_val": lambda v: f"{v:,.1f} t CO₂e/yil",
        "m_co2_delta": lambda d, pct: f"{d:+,.1f} t ({pct})",
        "m_co2_help": lambda pct: f"Butun mahsulot hayotiy sikli boʻyicha oʻzgarish (xom sut va qayta ishlash bilan birga): {pct}.",
        "m_plastic": "Birlamchi plastik sarfi",
        "m_plastic_val": lambda v: f"{v:,.1f} t/yil",
        "m_plastic_delta": lambda d, pct: f"{d:+,.1f} t ({pct})",
        "m_plastic_help": "Yil davomida sarflanadigan birlamchi qazilma polimer xomashyosi (ikkilamchi granulalar kirmaydi).",
        "m_waste": "Poligon va yoqishga ketadigan chiqindi",
        "m_waste_val": lambda v: f"{v:,.1f} t/yil",
        "m_waste_delta": lambda d, pct: f"{d:+,.1f} t ({pct})",
        "m_waste_help": lambda rec: f"Chiqindixona (poligon) yoki yoqishga yuboriladigan qadoq chiqindisi. Qayta ishlangan qadoq: {rec:,.1f} t/yil.",
        "m_water": "Suv sarfi",
        "m_water_val": lambda v: f"{v:,.0f} m³/yil",
        "m_water_delta": lambda d, pct: f"{d:+,.0f} m³ ({pct})",
        "m_water_help": "Qadoq materiallarini ishlab chiqarish va koʻp martalik idishlarni yuvish uchun sarflangan suv.",
        "m_energy": "Energiya talabi",
        "m_energy_val": lambda v: f"{v:,.0f} GJ/yil",
        "m_energy_delta": lambda d, pct: f"{d:+,.0f} GJ ({pct})",
        "m_energy_help": "Qadoq ishlab chiqarish, shakl berish va yuvish jarayonlarida sarflangan jami energiya.",
        # Section 4: Visual comparison
        "sec4_title": "4. Yonma-yon taqqoslash: Joriy va Taklif etilayotgan qadoq",
        "badge_current_card": "Joriy qadoqlash (Bazaviy)",
        "badge_proposed_card": "Taklif etilayotgan qadoqlash (Muqobil)",
        "lbl_cost_per_pkg": "1 dona qadoq xarajati",
        "lbl_co2_per_pkg": "1 dona qadoq uglerod izi",
        "lbl_pkg_weight": "Boʻsh qadoq vazni",
        "reusable_yes": lambda trips: f"Koʻp martalik ({trips:.1f} marta aylanadi)",
        "reusable_no": "Bir martalik",
        "card_bullets": lambda mat, fmt, rec, eol, spoil_pct, spoil_t: (
            f"- **Asosiy material:** {mat} ({fmt})\n"
            f"- **Ikkilamchi xomashyo ulushi:** {rec} | **Qayta ishlash darajasi:** {eol}\n"
            f"- **Mahsulot yoʻqotilishi (spoilage):** {spoil_pct} (yiliga {spoil_t:,.1f} tonna)"
        ),
        "chart_cost_title": "Yillik qadoqlash xarajatlari tarkibi ($ / yil)",
        "chart_cost_x": "Yillik xarajat ($ / yil)",
        "chart_co2_title": "Bosqichlar boʻyicha yillik uglerod chiqindilari (tonna CO₂e / yil)",
        "chart_co2_x": "Yillik chiqindilar (tonna CO₂e / yil)",
        "scen_current": "Joriy qadoqlash",
        "scen_proposed": "Taklif etilayotgan qadoqlash",
        "scen_alt": "Muqobil variant",
        "cost_drivers": {
            "raw": "Xomashyo va qopqoqlar",
            "spoilage": "Mahsulot nobudgarchiligi",
            "freight": "Transport va logistika",
            "washing": "Idishlarni yuvish (koʻp martalik)",
            "waste": "Chiqindi utilizatsiyasi",
        },
        "co2_stages": {
            "raw": "Xomashyo (polimer, karton, shisha)",
            "converting": "Qadoqqa shakl berish (qoliplash)",
            "spoilage": "Mahsulot yoʻqotilishi uglerod izi",
            "transport": "Transport va teskari logistika",
            "washing_eol": "Yuvish va chiqindini qayta ishlash",
        },
        # Expanders
        "exp_all_options": "Ushbu mahsulot uchun barcha mos qadoqlash turlarini solishtirish",
        "exp_all_caption": "Har bir mos qadoqlash turining yillik xarajati va uglerod izini joriy qadoq bilan taqqoslang.",
        "col_option": "Qadoqlash varianti",
        "col_selection": "Holati",
        "col_ann_cost": "Yillik xarajat ($/yil)",
        "col_cost_diff": "Xarajat farqi ($/yil)",
        "col_co2": "Uglerod izi CO₂e (t/yil)",
        "col_co2_pct": "CO₂e oʻzgarishi (%)",
        "col_plastic": "Birlamchi plastik (t/yil)",
        "col_payback": "Qoplanish muddati (yil)",
        "col_decision": "Xulosa",
        "exp_provenance": "Maʼlumot manbalari, noaniqlik va sezgirlik tahlili",
        "sens_title": "Natijalarga nima eng koʻp taʼsir qiladi? (±20% sezgirlik tahlili)",
        "sens_caption": lambda pkg_name, tonnes: (
            f"Bozor narxlari va operatsion koʻrsatkichlarning ±20% oʻzgarishi **{pkg_name}** variantiga taʼsiri (**{tonnes:,} tonna/yil** uchun)."
        ),
        "col_sens_param": "Asosiy parametr",
        "col_sens_cost": "Yillik xarajat tebranishi ($/yil)",
        "col_sens_co2": "Yillik CO₂e tebranishi (t/yil)",
        "prov_title": "Tasdiqlangan ilmiy maʼlumotlar va ssenariy farazlari",
        "prov_alert_title": "Maʼlumotlar manbasi va cheklovlar",
        "prov_body": (
            "- **Tasdiqlangan xalqaro LCA maʼlumotlari (`published_reference`):**\n"
            "  - **AGRIBALYSE 3.2 (ADEME / INRAE):** Qadoqsiz sut mahsulotlarining bazaviy ekologik izi "
            "(ikki marta hisoblanmasligi uchun bazaviy `Emballage` bosqichi ayirib tashlangan).\n"
            "  - **NIST / Argonne GREET 2024:** Mintaqalar boʻyicha birlamchi va ikkilamchi polimerlar uglerod izi.\n"
            "  - **USLCI (NREL) va ilmiy manbalar:** Karton, shisha, alyuminiy, qoliplash va yuk tashish koʻrsatkichlari.\n"
            "  - **IFC / Jahon banki (2007):** Sutni qayta ishlashda energiya, suv va qadoq massasi meʼyorlari.\n"
            "- **Ssenariy farazlari (`assumed` / `proxy`):**\n"
            "  - Xomashyo narxlari, CAPEX va tariflar ssenariy bahosi boʻlib, yakuniy investitsiya qaroridan oldin "
            "mahalliy yetkazib beruvchilarning tijorat takliflari bilan aniqlashtirilishi lozim."
        ),
        "btn_download": "Toʻliq ssenariy hisobotini yuklab olish (.md)",
        "lbl_dev_mode": "Dasturchi rejimi (Dev Mode)",
        "lbl_mat_price_adj": "Taklif etilayotgan qadoq xomashyo narxi oʻzgarishi (%)",
        "m_capex": "Boshlangʻich investitsiya (CAPEX)",
        "m_capex_delta": lambda eq, inst: f"Uskuna {eq} + Oʻrnatish {inst}",
        "m_inc_cf": "Yillik qoʻshimcha sof pul oqimi",
        "m_payback_yrs_mos": lambda y, m: f"{y:.2f} yil ({m:.1f} oy)",
        "m_cum_cf": lambda yrs: f"{yrs} yillik jami sof pul oqimi",
        "exp_cf_schedule": "Yillar boʻyicha jami pul oqimi va oʻzini oqlash jadvali",
    },
    "ru": {
        "language_label": "Язык платформы",
        "brand_subtitle": "DairyEco AI — Платформа поддержки управленческих решений",
        "main_title": "Что изменится при переходе на другую упаковку молочной продукции?",
        "main_caption": (
            "Сравните экономический и экологический эффект перехода с текущей упаковки на альтернативную — "
            "на базе верифицированных данных ОЖЦ (`AGRIBALYSE 3.2`, `NIST 2024`, `USLCI`, `IFC 2007`)."
        ),
        "sec1_title": "1. Настройте сценарий перехода на новую упаковку",
        "lbl_category": "Категория молочной продукции",
        "lbl_product": "Конкретный молочный продукт",
        "lbl_volume": "Годовой объём производства (тонн / год)",
        "hlp_volume": "1 тонна = 1 000 кг товарного молочного продукта, доставленного покупателю.",
        "lbl_current_pkg": "Текущая упаковка (базовый вариант)",
        "lbl_proposed_pkg": "Предлагаемая альтернативная упаковка",
        "lbl_check_compat": " [Проверьте совместимость]",
        "lbl_period": "Горизонт сравнения",
        "fmt_years": lambda y: f"{y} {'год' if y == 1 else ('года' if y in (2, 3, 4) else 'лет')}",
        "exp_assumptions": "Настроить финансовые, капитальные (CAPEX) и региональные параметры",
        "lbl_capex": "Инвестиции в оборудование / CAPEX ($)",
        "hlp_capex": "Единовременные затраты на модернизацию упаковочной линии или закупку оборудования.",
        "lbl_install": "Монтаж и пусконаладка ($)",
        "lbl_selling_price": "Чистая отпускная цена продукта ($ / кг)",
        "hlp_selling_price": "Используется для расчёта годовой выручки и маржинальной прибыли.",
        "lbl_spoilage_cost": "Себестоимость потерь продукта ($ / кг)",
        "hlp_spoilage_cost": "Себестоимость молочного продукта, потерянного из-за боя или разгерметизации упаковки.",
        "lbl_resin_region": "Регион производства полимеров (NIST 2024)",
        "lbl_grid": "Углеродоёмкость электросети",
        "lbl_discount": "Годовая ставка дисконтирования для NPV (%)",
        "lbl_return_rate": "Доля возврата оборотной бутылки (%)",
        "hlp_return_rate": "Применяется при оценке возвратной стеклянной тары.",
        # Decision classifications
        "verdict_infeasible": "Технически несовместимо с выбранным молочным продуктом",
        "badge_infeasible": "Несовместимый формат",
        "verdict_win_win": "Выгодно и экономически, и экологически (Win-Win)",
        "badge_win_win": "Рекомендуется: двойная выгода (Win-Win)",
        "verdict_env_only": "Экологически выгодно, но требует дополнительных затрат",
        "badge_env_only": "Экологическая инвестиция (снижает выбросы, дороже)",
        "verdict_econ_only": "Экономически выгодно, но увеличивает нагрузку на среду",
        "badge_econ_only": "Финансовая экономия (дешевле, но выше выбросы)",
        "verdict_neither": "Не выгодно ни экономически, ни экологически",
        "badge_neither": "Не рекомендуется (выше затраты и выше выбросы)",
        "verdict_baseline": "Текущий базовый вариант",
        "cum_box_caption": lambda yrs: f"Суммарный финансовый и углеродный эффект за {yrs} лет",
        "cum_net_cash": lambda yrs, val: f"- **Чистый денежный эффект за {yrs} лет (с учётом CAPEX):** **{val}**",
        "cum_co2": lambda yrs, val: f"- **Суммарное изменение выбросов CO₂e за {yrs} лет:** **{val:+.1f} т CO₂e**",
        "cum_plastic": lambda yrs, val: f"- **Изменение расхода первичного пластика за {yrs} лет:** **{val:+.1f} т**",
        "err_infeasible_title": "Нарушение технологической совместимости",
        "warn_operational_title": "Производственное примечание",
        # Section 2: Business impact
        "sec2_title": "2. Экономический и финансовый эффект",
        "sec2_caption": lambda tonnes, yrs, inv, disc: (
            f"Экономика сценария для объёма **{tonnes:,} тонн/год** на горизонте **{yrs} лет** "
            f"(капитальные затраты CAPEX + монтаж: **{inv}**; ставка дисконтирования: **{disc:.1f}%**)."
        ),
        "m_prop_cost": "Годовые затраты на новую упаковку",
        "m_prop_cost_delta": lambda pct, base_val: f"{pct} к текущим ({base_val})",
        "m_prop_cost_help": "Включает стоимость материалов, логистику, мойку оборотной тары, утилизацию отходов и потери молочного продукта.",
        "m_savings_pos": "Годовая экономия затрат",
        "m_savings_neg": "Дополнительные годовые расходы",
        "m_savings_val": lambda val: f"{val} / год",
        "m_savings_delta": lambda val, yrs: f"{val} за {yrs} лет",
        "m_savings_help": "Годовая разница операционных затрат (Текущие затраты минус Предлагаемые).",
        "m_payback": "Срок окупаемости (Payback)",
        "m_payback_yrs": lambda y: f"{y:.1f} лет",
        "m_payback_within": "Окупается в пределах горизонта",
        "m_payback_exceeds": lambda yrs: f"Превышает горизонт ({yrs} лет)",
        "m_payback_immediate": "Мгновенно (0 лет)",
        "m_payback_no_capex": "Не требует начальных CAPEX",
        "m_payback_none": "Не окупается",
        "m_payback_cost_up": "Операционные затраты растут",
        "m_payback_help": lambda inv: f"Начальные инвестиции {inv}, делённые на годовую экономию операционных затрат.",
        "m_npv": lambda yrs: f"Чистая приведённая стоимость (NPV за {yrs} лет)",
        "m_be_vol": lambda t: f"Безубыточность: {t:,.0f} т/год",
        "m_be_none": "Нет точки безубыточности по объёму",
        "m_npv_help": "Дисконтированный денежный поток перехода с учётом начальных капитальных вложений.",
        "m_margin": "Годовая маржинальная прибыль",
        "m_margin_delta": lambda val: f"{val} / год к марже",
        "m_margin_help": "Расчётная годовая выручка за вычетом упаковочных и заводских операционных затрат.",
        # Section 3: Environmental impact
        "sec3_title": "3. Экологическое воздействие",
        "sec3_caption": "Годовой экологический след производства упаковочного сырья, формования, логистики, мойки, утилизации и потерь продукта.",
        "m_co2": "Углеродный след упаковки (CO₂e)",
        "m_co2_val": lambda v: f"{v:,.1f} т CO₂e/год",
        "m_co2_delta": lambda d, pct: f"{d:+,.1f} т ({pct})",
        "m_co2_help": lambda pct: f"Изменение полного углеродного следа продукта (включая сырое молоко и переработку): {pct}.",
        "m_plastic": "Расход первичного пластика",
        "m_plastic_val": lambda v: f"{v:,.1f} т/год",
        "m_plastic_delta": lambda d, pct: f"{d:+,.1f} т ({pct})",
        "m_plastic_help": "Годовая масса первичных ископаемых полимеров (без учёта вторичного гранулята и биополимеров).",
        "m_waste": "Отходы на полигон и сжигание",
        "m_waste_val": lambda v: f"{v:,.1f} т/год",
        "m_waste_delta": lambda d, pct: f"{d:+,.1f} т ({pct})",
        "m_waste_help": lambda rec: f"Масса упаковки, направляемой на захоронение или сжигание. Перерабатываемая масса: {rec:,.1f} т/год.",
        "m_water": "Потребление воды",
        "m_water_val": lambda v: f"{v:,.0f} м³/год",
        "m_water_delta": lambda d, pct: f"{d:+,.0f} м³ ({pct})",
        "m_water_help": "Вода на производство упаковочных материалов плюс мойка возвратной тары.",
        "m_energy": "Энергопотребление упаковки",
        "m_energy_val": lambda v: f"{v:,.0f} ГДж/год",
        "m_energy_delta": lambda d, pct: f"{d:+,.0f} ГДж ({pct})",
        "m_energy_help": "Затраты ископаемой и электрической энергии на производство, формование и мойку упаковки.",
        # Section 4: Visual comparison
        "sec4_title": "4. Наглядное сравнение: Текущая vs. Предлагаемая упаковка",
        "badge_current_card": "Текущая упаковка (База)",
        "badge_proposed_card": "Предлагаемая упаковка (Альтернатива)",
        "lbl_cost_per_pkg": "Затраты на 1 упаковку",
        "lbl_co2_per_pkg": "Выбросы на 1 упаковку",
        "lbl_pkg_weight": "Масса пустой упаковки",
        "reusable_yes": lambda trips: f"Возвратная ({trips:.1f} эфф. циклов)",
        "reusable_no": "Одноразовая",
        "card_bullets": lambda mat, fmt, rec, eol, spoil_pct, spoil_t: (
            f"- **Основной материал:** {mat} ({fmt})\n"
            f"- **Доля вторсырья:** {rec} | **Переработка после использования:** {eol}\n"
            f"- **Потери продукта (порча/бой):** {spoil_pct} ({spoil_t:,.1f} тонн/год)"
        ),
        "chart_cost_title": "Структура годовых затрат на упаковку ($ / год)",
        "chart_cost_x": "Годовые затраты ($ / год)",
        "chart_co2_title": "Годовые выбросы углерода по этапам жизненного цикла (тонн CO₂e / год)",
        "chart_co2_x": "Годовые выбросы (тонн CO₂e / год)",
        "scen_current": "Текущая упаковка",
        "scen_proposed": "Предлагаемая упаковка",
        "scen_alt": "Альтернатива",
        "cost_drivers": {
            "raw": "Сырьё, материалы и крышки",
            "spoilage": "Потери и порча молочного продукта",
            "freight": "Транспорт и дистрибуция",
            "washing": "Мойка оборотной тары",
            "waste": "Утилизация отходов (за вычетом вторсырья)",
        },
        "co2_stages": {
            "raw": "Сырьё (полимеры, картон, стекло)",
            "converting": "Формование и производство тары",
            "spoilage": "Углеродный след потерь продукта",
            "transport": "Транспорт и обратная логистика",
            "washing_eol": "Мойка тары и конец жизненного цикла",
        },
        # Expanders
        "exp_all_options": "Сравнить все совместимые варианты упаковки для этого продукта",
        "exp_all_caption": "Сравните все подходящие форматы упаковки с вашей текущей упаковкой по годовым затратам и углеродному следу.",
        "col_option": "Вариант упаковки",
        "col_selection": "Статус",
        "col_ann_cost": "Годовые затраты ($/год)",
        "col_cost_diff": "Изменение затрат ($/год)",
        "col_co2": "Выбросы CO₂e (т/год)",
        "col_co2_pct": "Изменение CO₂e (%)",
        "col_plastic": "Первичный пластик (т/год)",
        "col_payback": "Окупаемость (лет)",
        "col_decision": "Резюме решения",
        "exp_provenance": "Источники данных, неопределённость и анализ чувствительности",
        "sens_title": "Что сильнее всего влияет на результат? (чувствительность ±20%)",
        "sens_caption": lambda pkg_name, tonnes: (
            f"Влияние колебаний рыночных цен и операционных параметров (±20%) для варианта **{pkg_name}** (на объём **{tonnes:,} тонн/год**)."
        ),
        "col_sens_param": "Ключевой параметр",
        "col_sens_cost": "Размах годовых затрат ($/год)",
        "col_sens_co2": "Размах выбросов CO₂e (т/год)",
        "prov_title": "Опубликованные справочные данные vs. сценарные допущения",
        "prov_alert_title": "Происхождение данных и ограничения",
        "prov_body": (
            "- **Опубликованные справочные базы ОЖЦ (`published_reference`):**\n"
            "  - **AGRIBALYSE 3.2 (ADEME / INRAE):** Углеродный след молочных продуктов без упаковки "
            "(базовый этап `Emballage` вычтен во избежание двойного счёта).\n"
            "  - **NIST / Argonne GREET 2024:** Региональные коэффициенты для первичных и вторичных полимеров.\n"
            "  - **USLCI (NREL) и литературные данные:** Картон, стекло, алюминий, формование и грузоперевозки.\n"
            "  - **IFC / Всемирный банк (2007):** Нормативы расхода энергии, воды и массы упаковки молочных заводов.\n"
            "- **Сценарные допущения (`assumed` / `proxy`):**\n"
            "  - Цены на гранулят/картон, CAPEX и тарифы являются настраиваемыми сценарными оценками и перед принятием "
            "инвестиционного решения должны быть уточнены по коммерческим предложениям поставщиков."
        ),
        "btn_download": "Скачать полный отчёт по сценарию (.md)",
        "lbl_dev_mode": "Режим разработчика (Dev Mode)",
        "lbl_mat_price_adj": "Корректировка цены сырья новой упаковки (%)",
        "m_capex": "Начальные инвестиции (CAPEX)",
        "m_capex_delta": lambda eq, inst: f"Оборуд. {eq} + Монтаж {inst}",
        "m_inc_cf": "Годовой приростной денежный поток",
        "m_payback_yrs_mos": lambda y, m: f"{y:.2f} г. ({m:.1f} мес.)",
        "m_cum_cf": lambda yrs: f"Кумулятивный денежный поток ({yrs} лет)",
        "exp_cf_schedule": "Показать график кумулятивного денежного потока и окупаемости по годам",
    },
}


def localize_payback_explanation(
    lang: str,
    payback_status: str,
    initial_investment: float,
    annual_cf: float,
    horizon_years: int,
    payback_years: float | None,
    payback_months: float | None,
    unconstrained_years: float | None,
    cum_net_cf: float,
    fallback_en: str,
) -> str:
    """Return a clear, localized explanation of the payback calculation and status."""
    if lang == "en":
        return fallback_en

    if lang == "uz":
        if payback_status == "immediate":
            return (
                f"Darhol oʻzini oqlaydi (0,00 yil / 0,0 oy): boshlangʻich CAPEX $0 boʻlib, "
                f"yillik qoʻshimcha sof pul oqimi +${annual_cf:,.0f}/yil ni tashkil etadi."
            )
        if payback_status == "within_horizon" and payback_years is not None and payback_months is not None:
            return (
                f"Investitsiya {payback_years:.2f} yilda ({payback_months:.1f} oyda) toʻliq qoplanadi: "
                f"yillik +${annual_cf:,.0f} tejamkorlik hisobiga ${initial_investment:,.0f} boshlangʻich CAPEX "
                f"{horizon_years} yillik davr ichida oʻzini oqlaydi (jami sof pul oqimi: +${cum_net_cf:,.0f})."
            )
        if payback_status == "exceeds_horizon" and unconstrained_years is not None:
            return (
                f"{horizon_years} yillik davr ichida oʻzini qoplamaydi: yillik +${annual_cf:,.0f} ijobiy pul oqimi "
                f"{horizon_years} yilda ${annual_cf * horizon_years:,.0f} ni qaytaradi (qoplanmagan qoldiq: "
                f"-${abs(cum_net_cf):,.0f}). ${initial_investment:,.0f} CAPEX toʻliq qoplanishi uchun "
                f"{unconstrained_years:.2f} yil ({unconstrained_years * 12.0:.1f} oy) talab etiladi."
            )
        return (
            f"Oʻzini qoplamaydi: yillik qoʻshimcha pul oqimi manfiy (-${abs(annual_cf):,.0f}/yil), "
            f"yaʼni taklif etilayotgan qadoq joriy qadoqdan qimmatroq. Shu sababli ${initial_investment:,.0f} CAPEX "
            f"qoplanmaydi ({horizon_years} yillik jami pul oqimi: -${abs(cum_net_cf):,.0f})."
        )

    # Russian (ru)
    if payback_status == "immediate":
        return (
            f"Мгновенная окупаемость (0,00 лет / 0,0 мес.): начальные CAPEX равны $0 при "
            f"положительном приростном денежном потоке +${annual_cf:,.0f}/год."
        )
    if payback_status == "within_horizon" and payback_years is not None and payback_months is not None:
        return (
            f"Окупаемость достигается за {payback_years:.2f} года ({payback_months:.1f} мес.): "
            f"приростной денежный поток +${annual_cf:,.0f}/год полностью возмещает ${initial_investment:,.0f} CAPEX "
            f"в пределах горизонта {horizon_years} лет (кумулятивный чистый поток: +${cum_net_cf:,.0f})."
        )
    if payback_status == "exceeds_horizon" and unconstrained_years is not None:
        return (
            f"Не окупается в пределах горизонта {horizon_years} лет: положительный поток +${annual_cf:,.0f}/год "
            f"возмещает ${annual_cf * horizon_years:,.0f} за {horizon_years} лет (остаток непокрытых CAPEX: "
            f"-${abs(cum_net_cf):,.0f}). Для полной окупаемости ${initial_investment:,.0f} требуется "
            f"{unconstrained_years:.2f} года ({unconstrained_years * 12.0:.1f} мес.)."
        )
    return (
        f"Не окупается: годовой приростной денежный поток отрицателен (-${abs(annual_cf):,.0f}/год, "
        f"предлагаемая упаковка дороже базовой в эксплуатации), поэтому начальные инвестиции ${initial_investment:,.0f} "
        f"не возмещаются (кумулятивный поток за {horizon_years} лет: -${abs(cum_net_cf):,.0f})."
    )


def build_plain_language_narrative(
    lang: str,
    annual_tonnes: int,
    product_name: str,
    base_pkg_name: str,
    prop_pkg_name: str,
    diff_annual_pkg_co2_t: float,
    delta_pkg_gwp_pct_str: str,
    diff_annual_plastic_t: float,
    annual_cost_diff: float,
    delta_cost_pct: float,
    cost_diff_formatted: str,
) -> str:
    """Build the plain-language executive summary paragraph in English, Uzbek, or Russian."""
    if lang == "uz":
        co2_dir = "kamaytiradi" if diff_annual_pkg_co2_t <= 0 else "oshiradi"
        if diff_annual_plastic_t < -0.001:
            plastic_part = (
                f"birlamchi plastik sarfini yiliga **{abs(diff_annual_plastic_t):,.1f} tonnaga** "
                f"({abs(diff_annual_plastic_t * 1000):,.0f} kg/yil) qisqartiradi"
            )
        elif diff_annual_plastic_t > 0.001:
            plastic_part = (
                f"birlamchi plastik sarfini yiliga **{diff_annual_plastic_t:,.1f} tonnaga** oshiradi"
            )
        else:
            plastic_part = "birlamchi plastik sarfini oʻzgartirmaydi"

        if annual_cost_diff <= 0:
            cost_part = (
                f"qadoqlash va mahsulot yoʻqotilishi xarajatlaridan yiliga **{cost_diff_formatted}** "
                f"(**{abs(delta_cost_pct):.1f}%**) tejash imkonini beradi"
            )
        else:
            cost_part = (
                f"yillik qadoqlash operatsion xarajatlarini **{cost_diff_formatted}** ga "
                f"(**+{delta_cost_pct:.1f}%**) oshiradi"
            )

        return (
            f"Yiliga **{annual_tonnes:,} tonna** **{product_name}** ishlab chiqarilganda, "
            f"**{base_pkg_name}** oʻrniga **{prop_pkg_name}** qadoqlash turiga oʻtish yillik uglerod "
            f"(CO₂e) chiqindilarini **{abs(diff_annual_pkg_co2_t):,.1f} tonnaga** (**{delta_pkg_gwp_pct_str}**) {co2_dir} "
            f"hamda {plastic_part}; shu bilan birga bu oʻzgarish {cost_part}."
        )

    if lang == "ru":
        co2_dir = "снижает" if diff_annual_pkg_co2_t <= 0 else "увеличивает"
        if diff_annual_plastic_t < -0.001:
            plastic_part = (
                f"сокращает потребление первичного пластика на **{abs(diff_annual_plastic_t):,.1f} тонн/год** "
                f"({abs(diff_annual_plastic_t * 1000):,.0f} кг/год)"
            )
        elif diff_annual_plastic_t > 0.001:
            plastic_part = (
                f"увеличивает потребление первичного пластика на **{diff_annual_plastic_t:,.1f} тонн/год**"
            )
        else:
            plastic_part = "оставляет расход первичного пластика без изменений"

        if annual_cost_diff <= 0:
            cost_part = (
                f"экономит **{cost_diff_formatted}/год** на упаковке и снижении потерь продукта "
                f"(затраты на упаковку ниже на **{abs(delta_cost_pct):.1f}%**)"
            )
        else:
            cost_part = (
                f"увеличивает операционные затраты на упаковку на **{cost_diff_formatted}/год** "
                f"(**+{delta_cost_pct:.1f}%** к текущим затратам)"
            )

        return (
            f"При объёме производства **{annual_tonnes:,} тонн/год** продукта «**{product_name}**» "
            f"переход с упаковки «**{base_pkg_name}**» на «**{prop_pkg_name}**» {co2_dir} годовые выбросы "
            f"углерода на **{abs(diff_annual_pkg_co2_t):,.1f} т CO₂e/год** (**{delta_pkg_gwp_pct_str}**) и "
            f"{plastic_part}, при этом переход {cost_part}."
        )

    # Default English
    co2_verb = "reduces" if diff_annual_pkg_co2_t <= 0 else "increases"
    if diff_annual_plastic_t < -0.001:
        plastic_clause = (
            f"cuts virgin fossil plastic consumption by **{abs(diff_annual_plastic_t):,.1f} tonnes/year** "
            f"({abs(diff_annual_plastic_t * 1000):,.0f} kg/year)"
        )
    elif diff_annual_plastic_t > 0.001:
        plastic_clause = (
            f"increases virgin fossil plastic consumption by **{diff_annual_plastic_t:,.1f} tonnes/year**"
        )
    else:
        plastic_clause = "keeps virgin fossil plastic consumption unchanged"

    if annual_cost_diff <= 0:
        cost_clause = (
            f"saves **{cost_diff_formatted}/year** in packaging and spoilage costs "
            f"(**{abs(delta_cost_pct):.1f}%** lower packaging cost)"
        )
    else:
        cost_clause = (
            f"increases packaging operating expenses by **{cost_diff_formatted}/year** "
            f"(**+{delta_cost_pct:.1f}%** higher packaging cost)"
        )

    return (
        f"For **{annual_tonnes:,} tonnes/year** of **{product_name}**, switching from "
        f"**{base_pkg_name}** to **{prop_pkg_name}** {co2_verb} annual packaging carbon emissions "
        f"by **{abs(diff_annual_pkg_co2_t):,.1f} tonnes CO₂e/year** (**{delta_pkg_gwp_pct_str}**) "
        f"and {plastic_clause}, while it {cost_clause}."
    )
