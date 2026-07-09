"""ISO 3166-1 alpha-2 国コード -> UN M49 サブリージョン（22分類、global_v2と同じ区分）。

global_v2（旧リポジトリ, configs/global_v2_N100_clean.yaml）が使った
"Natural Earth admin-0 SUBREGION" と同じ22分類に合わせてある。
出典: UN Statistics Division M49 standard country/region grouping
(https://unstats.un.org/unsd/methodology/m49/)。ここでは実務上必要な国のみ収録
（Overture divisionsのcountryコードに存在するもの中心、抜けがあれば適宜追加）。
"""

ISO2_TO_SUBREGION: dict[str, str] = {
    # Northern Africa
    "EG": "Northern Africa", "LY": "Northern Africa", "TN": "Northern Africa",
    "DZ": "Northern Africa", "MA": "Northern Africa", "SD": "Northern Africa",
    "EH": "Northern Africa",
    # Eastern Africa
    "ET": "Eastern Africa", "KE": "Eastern Africa", "TZ": "Eastern Africa",
    "UG": "Eastern Africa", "SO": "Eastern Africa", "MZ": "Eastern Africa",
    "MG": "Eastern Africa", "ZW": "Eastern Africa", "ZM": "Eastern Africa",
    "MW": "Eastern Africa", "RW": "Eastern Africa", "BI": "Eastern Africa",
    "SS": "Eastern Africa", "DJ": "Eastern Africa", "ER": "Eastern Africa",
    "KM": "Eastern Africa", "SC": "Eastern Africa", "MU": "Eastern Africa",
    "RE": "Eastern Africa", "YT": "Eastern Africa",
    # Middle Africa
    "CD": "Middle Africa", "CM": "Middle Africa", "AO": "Middle Africa",
    "TD": "Middle Africa", "CF": "Middle Africa", "CG": "Middle Africa",
    "GA": "Middle Africa", "GQ": "Middle Africa", "ST": "Middle Africa",
    # Southern Africa
    "ZA": "Southern Africa", "NA": "Southern Africa", "BW": "Southern Africa",
    "LS": "Southern Africa", "SZ": "Southern Africa",
    # Western Africa
    "NG": "Western Africa", "GH": "Western Africa", "CI": "Western Africa",
    "NE": "Western Africa", "BF": "Western Africa", "ML": "Western Africa",
    "SN": "Western Africa", "GN": "Western Africa", "BJ": "Western Africa",
    "TG": "Western Africa", "SL": "Western Africa", "LR": "Western Africa",
    "MR": "Western Africa", "GM": "Western Africa", "GW": "Western Africa",
    "CV": "Western Africa", "GI": "Northern Africa",  # Gibraltar 便宜上
    # Northern America
    "US": "Northern America", "CA": "Northern America", "GL": "Northern America",
    "BM": "Northern America", "PM": "Northern America",
    # Central America
    "MX": "Central America", "GT": "Central America", "HN": "Central America",
    "NI": "Central America", "PA": "Central America", "CR": "Central America",
    "SV": "Central America", "BZ": "Central America",
    # Caribbean
    "CU": "Caribbean", "HT": "Caribbean", "DO": "Caribbean", "JM": "Caribbean",
    "TT": "Caribbean", "BS": "Caribbean", "BB": "Caribbean", "LC": "Caribbean",
    "GD": "Caribbean", "VC": "Caribbean", "AG": "Caribbean", "DM": "Caribbean",
    "KN": "Caribbean", "PR": "Caribbean", "VI": "Caribbean", "VG": "Caribbean",
    "AI": "Caribbean", "KY": "Caribbean", "TC": "Caribbean", "MS": "Caribbean",
    "GP": "Caribbean", "MQ": "Caribbean", "CW": "Caribbean", "AW": "Caribbean",
    "SX": "Caribbean", "BQ": "Caribbean",
    # South America
    "BR": "South America", "AR": "South America", "CO": "South America",
    "PE": "South America", "VE": "South America", "CL": "South America",
    "EC": "South America", "BO": "South America", "PY": "South America",
    "UY": "South America", "GY": "South America", "SR": "South America",
    "GF": "South America", "FK": "South America",
    # Northern Europe
    "GB": "Northern Europe", "IE": "Northern Europe", "SE": "Northern Europe",
    "NO": "Northern Europe", "FI": "Northern Europe", "DK": "Northern Europe",
    "IS": "Northern Europe", "EE": "Northern Europe", "LV": "Northern Europe",
    "LT": "Northern Europe", "FO": "Northern Europe", "AX": "Northern Europe",
    "SJ": "Northern Europe", "GG": "Northern Europe", "JE": "Northern Europe",
    "IM": "Northern Europe",
    # Western Europe
    "DE": "Western Europe", "FR": "Western Europe", "NL": "Western Europe",
    "BE": "Western Europe", "AT": "Western Europe", "CH": "Western Europe",
    "LU": "Western Europe", "LI": "Western Europe", "MC": "Western Europe",
    # Eastern Europe
    "RU": "Eastern Europe", "PL": "Eastern Europe", "UA": "Eastern Europe",
    "RO": "Eastern Europe", "CZ": "Eastern Europe", "HU": "Eastern Europe",
    "BY": "Eastern Europe", "BG": "Eastern Europe", "SK": "Eastern Europe",
    "MD": "Eastern Europe",
    # Southern Europe
    "IT": "Southern Europe", "ES": "Southern Europe", "GR": "Southern Europe",
    "PT": "Southern Europe", "HR": "Southern Europe", "RS": "Southern Europe",
    "BA": "Southern Europe", "AL": "Southern Europe", "SI": "Southern Europe",
    "MK": "Southern Europe", "ME": "Southern Europe", "MT": "Southern Europe",
    "AD": "Southern Europe", "SM": "Southern Europe", "VA": "Southern Europe",
    "XK": "Southern Europe", "CY": "Southern Europe",
    # Central Asia
    "KZ": "Central Asia", "UZ": "Central Asia", "TM": "Central Asia",
    "TJ": "Central Asia", "KG": "Central Asia",
    # Eastern Asia
    "CN": "Eastern Asia", "JP": "Eastern Asia", "KR": "Eastern Asia",
    "KP": "Eastern Asia", "MN": "Eastern Asia", "TW": "Eastern Asia",
    "HK": "Eastern Asia", "MO": "Eastern Asia",
    # South-Eastern Asia
    "ID": "South-Eastern Asia", "PH": "South-Eastern Asia", "VN": "South-Eastern Asia",
    "TH": "South-Eastern Asia", "MM": "South-Eastern Asia", "MY": "South-Eastern Asia",
    "KH": "South-Eastern Asia", "LA": "South-Eastern Asia", "SG": "South-Eastern Asia",
    "TL": "South-Eastern Asia", "BN": "South-Eastern Asia",
    # Southern Asia
    "IN": "Southern Asia", "PK": "Southern Asia", "BD": "Southern Asia",
    "AF": "Southern Asia", "NP": "Southern Asia", "LK": "Southern Asia",
    "BT": "Southern Asia", "MV": "Southern Asia", "IR": "Southern Asia",
    # Western Asia
    "TR": "Western Asia", "SA": "Western Asia", "IQ": "Western Asia",
    "YE": "Western Asia", "SY": "Western Asia", "JO": "Western Asia",
    "AE": "Western Asia", "IL": "Western Asia", "PS": "Western Asia",
    "LB": "Western Asia", "OM": "Western Asia", "KW": "Western Asia",
    "QA": "Western Asia", "BH": "Western Asia", "GE": "Western Asia",
    "AM": "Western Asia", "AZ": "Western Asia",
    # Australia and New Zealand
    "AU": "Australia and New Zealand", "NZ": "Australia and New Zealand",
    # Melanesia
    "PG": "Melanesia", "FJ": "Melanesia", "SB": "Melanesia", "VU": "Melanesia",
    "NC": "Melanesia",
    # Micronesia
    "FM": "Micronesia", "KI": "Micronesia", "MH": "Micronesia", "NR": "Micronesia",
    "PW": "Micronesia", "GU": "Micronesia", "MP": "Micronesia",
    # Polynesia
    "PF": "Polynesia", "WS": "Polynesia", "TO": "Polynesia", "TV": "Polynesia",
    "CK": "Polynesia", "NU": "Polynesia", "WF": "Polynesia", "AS": "Polynesia",
    "PN": "Polynesia", "TK": "Polynesia",
}

SUBREGIONS_22 = sorted(set(ISO2_TO_SUBREGION.values()))
assert len(SUBREGIONS_22) == 22, f"想定22分類のはずが{len(SUBREGIONS_22)}分類になっている: {SUBREGIONS_22}"
