import re
from collections import Counter


# ==================================================
# COUNTRY ALIASES
#
# Deliberately conservative.
# A project country is only activated when it appears
# in at least two different speech scenes.
# ==================================================

COUNTRY_ALIASES = {

    "serbia": (
        "serbia",
        "serbian",
    ),

    "vietnam": (
        "vietnam",
        "viet nam",
        "vietnamese",
    ),

    "india": (
        "india",
        "indian",
    ),

    "south africa": (
        "south africa",
        "south african",
    ),

    "slovenia": (
        "slovenia",
        "slovenian",
    ),

    "singapore": (
        "singapore",
    ),

    "united arab emirates": (
        "united arab emirates",
        "uae",
    ),

    "netherlands": (
        "netherlands",
        "the netherlands",
        "dutch",
    ),

    "italy": (
        "italy",
        "italian",
    ),

    "belgium": (
        "belgium",
        "belgian",
    ),

    "hungary": (
        "hungary",
        "hungarian",
    ),

    "united kingdom": (
        "united kingdom",
        "great britain",
        "britain",
        "british",
    ),

    "south korea": (
        "south korea",
        "south korean",
    ),

    "france": (
        "france",
        "french",
    ),

    "germany": (
        "germany",
        "german",
    ),

    "spain": (
        "spain",
        "spanish",
    ),

    "portugal": (
        "portugal",
        "portuguese",
    ),

    "greece": (
        "greece",
        "greek",
    ),

    "croatia": (
        "croatia",
        "croatian",
    ),

    "bosnia and herzegovina": (
        "bosnia and herzegovina",
        "bosnia",
        "bosnian",
    ),

    "montenegro": (
        "montenegro",
        "montenegrin",
    ),

    "north macedonia": (
        "north macedonia",
        "macedonian",
    ),

    "romania": (
        "romania",
        "romanian",
    ),

    "bulgaria": (
        "bulgaria",
        "bulgarian",
    ),

    "austria": (
        "austria",
        "austrian",
    ),

    "switzerland": (
        "switzerland",
        "swiss",
    ),

    "czech republic": (
        "czech republic",
        "czechia",
        "czech",
    ),

    "slovakia": (
        "slovakia",
        "slovak",
    ),

    "poland": (
        "poland",
        "polish",
    ),

    "ukraine": (
        "ukraine",
        "ukrainian",
    ),

    "russia": (
        "russia",
        "russian",
    ),

    "united states": (
        "united states",
        "united states of america",
        "usa",
        "u.s.a",
    ),

    "canada": (
        "canada",
        "canadian",
    ),

    "mexico": (
        "mexico",
        "mexican",
    ),

    "brazil": (
        "brazil",
        "brazilian",
    ),

    "argentina": (
        "argentina",
        "argentinian",
    ),

    "australia": (
        "australia",
        "australian",
    ),

    "japan": (
        "japan",
        "japanese",
    ),

    "china": (
        "china",
        "chinese",
    ),

    "thailand": (
        "thailand",
        "thai",
    ),

    "indonesia": (
        "indonesia",
        "indonesian",
    ),

    "malaysia": (
        "malaysia",
        "malaysian",
    ),

    "philippines": (
        "philippines",
        "filipino",
    ),

    "cambodia": (
        "cambodia",
        "cambodian",
    ),

    "laos": (
        "laos",
        "laotian",
    ),

    "myanmar": (
        "myanmar",
        "burma",
        "burmese",
    ),

    "turkey": (
        "turkiye",
        "turkey",
        "turkish",
    ),

    "egypt": (
        "egypt",
        "egyptian",
    ),

    "morocco": (
        "morocco",
        "moroccan",
    ),

    "algeria": (
        "algeria",
        "algerian",
    ),

    "tunisia": (
        "tunisia",
        "tunisian",
    ),

    "saudi arabia": (
        "saudi arabia",
        "saudi",
    ),

    "qatar": (
        "qatar",
        "qatari",
    ),
}


COUNTRY_DISPLAY = {

    key:
        " ".join(
            word.capitalize()
            for word in key.split()
        )

    for key
    in COUNTRY_ALIASES
}


COUNTRY_DISPLAY.update({

    "united states":
        "United States",

    "united kingdom":
        "United Kingdom",

    "united arab emirates":
        "United Arab Emirates",

    "south africa":
        "South Africa",

    "south korea":
        "South Korea",

    "north macedonia":
        "North Macedonia",

    "bosnia and herzegovina":
        "Bosnia and Herzegovina",

    "czech republic":
        "Czech Republic",
})


# ==================================================
# HIGH-CONFIDENCE CITY / PLACE HINTS
#
# Only explicit metadata is used.
# Unknown metadata is NOT rejected.
# ==================================================

PLACE_COUNTRY_HINTS = {

    "belgrade":
        "serbia",

    "beograd":
        "serbia",

    "novi sad":
        "serbia",

    "budapest":
        "hungary",

    "venice":
        "italy",

    "venetian":
        "italy",

    "oostende":
        "belgium",

    "ostend":
        "belgium",

    "the hague":
        "netherlands",

    "amsterdam":
        "netherlands",

    "bled":
        "slovenia",

    "dubai":
        "united arab emirates",

    "abu dhabi":
        "united arab emirates",

    "seoul":
        "south korea",

    "london":
        "united kingdom",

    "paris":
        "france",

    "berlin":
        "germany",

    "rome":
        "italy",

    "milan":
        "italy",

    "barcelona":
        "spain",

    "madrid":
        "spain",

    "lisbon":
        "portugal",

    "prague":
        "czech republic",

    "vienna":
        "austria",

    "zurich":
        "switzerland",

    "new york":
        "united states",

    "los angeles":
        "united states",

    "san francisco":
        "united states",

    "toronto":
        "canada",

    "sydney":
        "australia",

    "melbourne":
        "australia",

    "tokyo":
        "japan",

    "bangkok":
        "thailand",

    "hanoi":
        "vietnam",

    "ho chi minh":
        "vietnam",

    "saigon":
        "vietnam",

    "singapore":
        "singapore",

    "mumbai":
        "india",

    "delhi":
        "india",

    "cape town":
        "south africa",

    "johannesburg":
        "south africa",
}


# ==================================================
# NORMALIZE
# ==================================================

def _normalize(value):

    value = str(
        value
        or ""
    ).lower()

    value = value.replace(
        "_",
        " ",
    )

    value = value.replace(
        "-",
        " ",
    )

    value = value.replace(
        "/",
        " ",
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def _contains_phrase(
    text,
    phrase,
):

    text = _normalize(
        text
    )

    phrase = _normalize(
        phrase
    )

    if not phrase:
        return False

    pattern = (
        r"(?<![a-z0-9])"
        + re.escape(phrase)
        + r"(?![a-z0-9])"
    )

    return bool(
        re.search(
            pattern,
            text,
        )
    )


# ==================================================
# DETECT COUNTRY
# ==================================================

def detect_countries(
    text,
):

    text = _normalize(
        text
    )

    found = set()


    for country, aliases in (
        COUNTRY_ALIASES.items()
    ):

        for alias in aliases:

            if _contains_phrase(
                text,
                alias,
            ):

                found.add(
                    country
                )

                break


    for place, country in (
        PLACE_COUNTRY_HINTS.items()
    ):

        if _contains_phrase(
            text,
            place,
        ):

            found.add(
                country
            )


    return found


# ==================================================
# PROJECT COUNTRY
# ==================================================

def infer_project_country(
    scenes,
):

    counter = Counter()


    for scene in scenes:

        if (
            scene.get(
                "scene_type"
            )
            == "gap"
        ):
            continue


        analysis = scene.get(
            "analysis",
            {},
        )

        text = " ".join([

            str(
                scene.get(
                    "dialogue",
                    "",
                )
                or ""
            ),

            str(
                analysis.get(
                    "location",
                    "",
                )
                or ""
            ),

            str(
                analysis.get(
                    "context",
                    "",
                )
                or ""
            ),
        ])


        countries = detect_countries(
            text
        )


        # Count a country only once per scene.
        for country in countries:

            counter[
                country
            ] += 1


    if not counter:
        return None


    ordered = (
        counter.most_common()
    )

    best_country, best_count = (
        ordered[0]
    )


    # Conservative:
    # project geography must appear in >= 2 scenes.
    if best_count < 2:
        return None


    if len(ordered) > 1:

        second_count = (
            ordered[1][1]
        )

        # Ambiguous project.
        if (
            second_count
            == best_count
        ):
            return None


    return best_country


# ==================================================
# QUERY LOCATION CHECK
# ==================================================

def _already_mentions_country(
    text,
    country,
):

    detected = detect_countries(
        text
    )

    return country in detected


# ==================================================
# MANIFEST CONTEXT CARRYOVER
# ==================================================

def enrich_manifest_with_project_context(
    manifest,
):

    if not isinstance(
        manifest,
        dict,
    ):
        return manifest


    scenes = manifest.get(
        "scenes",
        [],
    )


    if not isinstance(
        scenes,
        list,
    ):
        return manifest


    required_country = (
        infer_project_country(
            scenes
        )
    )


    narration = " ".join(

        str(
            scene.get(
                "dialogue",
                "",
            )
            or ""
        ).strip()

        for scene in scenes

        if (
            scene.get(
                "dialogue"
            )
        )
    )


    # Keep context useful but bounded.
    narration = narration[
        :6000
    ]


    display_country = None


    if required_country:

        display_country = (
            COUNTRY_DISPLAY.get(
                required_country,
                required_country.title(),
            )
        )


    manifest[
        "project_context"
    ] = {

        "required_country":
            display_country,

        "required_country_key":
            required_country,

        "narration":
            narration,
    }


    for scene in scenes:

        scene[
            "project_context"
        ] = dict(
            manifest[
                "project_context"
            ]
        )


        if not required_country:
            continue


        if (
            scene.get(
                "scene_type"
            )
            == "gap"
        ):
            continue


        # ------------------------------------------
        # ANALYSIS CARRYOVER
        # ------------------------------------------

        analysis = scene.setdefault(
            "analysis",
            {},
        )


        original_location = str(
            analysis.get(
                "location",
                "",
            )
            or ""
        ).strip()


        analysis[
            "original_location"
        ] = original_location


        analysis[
            "project_country"
        ] = display_country


        if not _already_mentions_country(
            original_location,
            required_country,
        ):

            if original_location:

                analysis[
                    "location"
                ] = (
                    original_location
                    + "; project country: "
                    + display_country
                )

            else:

                analysis[
                    "location"
                ] = (
                    "Project country: "
                    + display_country
                )


        old_context = str(
            analysis.get(
                "context",
                "",
            )
            or ""
        ).strip()


        project_sentence = (
            "Project-wide geographic context: "
            + display_country
            + "."
        )


        if (
            display_country.lower()
            not in old_context.lower()
        ):

            analysis[
                "context"
            ] = (
                old_context
                + " "
                + project_sentence
            ).strip()


        # ------------------------------------------
        # SEARCH QUERY CARRYOVER
        # ------------------------------------------

        search = scene.setdefault(
            "search",
            {},
        )


        original_primary = str(
            search.get(
                "primary_keyword",
                "",
            )
            or ""
        ).strip()


        original_keywords = (
            search.get(
                "keywords",
                [],
            )
        )


        if not isinstance(
            original_keywords,
            list,
        ):

            original_keywords = []


        original_keywords = [

            str(item).strip()

            for item
            in original_keywords

            if str(item).strip()
        ]


        if (
            original_primary
            and
            not _already_mentions_country(
                original_primary,
                required_country,
            )
        ):

            targeted_primary = (
                display_country
                + " "
                + original_primary
            )

        else:

            targeted_primary = (
                original_primary
            )


        targeted_keywords = []


        for keyword in (
            original_keywords[:3]
        ):

            if _already_mentions_country(
                keyword,
                required_country,
            ):

                targeted_keywords.append(
                    keyword
                )

            else:

                targeted_keywords.append(
                    display_country
                    + " "
                    + keyword
                )


        combined = []


        for keyword in (
            targeted_keywords
            + original_keywords
        ):

            key = (
                keyword.lower()
            )

            if (
                keyword
                and
                key not in [
                    x.lower()
                    for x in combined
                ]
            ):

                combined.append(
                    keyword
                )


        search[
            "original_primary_keyword"
        ] = original_primary


        search[
            "primary_keyword"
        ] = targeted_primary


        # Keep query count controlled.
        search[
            "keywords"
        ] = combined[:6]


        scene[
            "context_carryover"
        ] = True


    return manifest


# ==================================================
# CANDIDATE GEOGRAPHY GUARD
# ==================================================

def filter_geography_candidates(
    scene,
    candidates,
):

    candidates = list(
        candidates
        or []
    )


    project_context = scene.get(
        "project_context",
        {},
    )


    required_country = (
        project_context.get(
            "required_country_key"
        )
    )


    if not required_country:

        return (
            candidates,
            [],
            False,
        )


    kept = []

    rejected = []


    for candidate in candidates:

        metadata_text = " ".join([

            str(
                candidate.get(
                    "title",
                    "",
                )
                or ""
            ),

            str(
                candidate.get(
                    "source_url",
                    "",
                )
                or ""
            ),

            str(
                candidate.get(
                    "photographer",
                    "",
                )
                or ""
            ),
        ])


        detected = detect_countries(
            metadata_text
        )


        if (
            detected
            and
            required_country
            not in detected
        ):

            rejected.append({

                "provider":
                    candidate.get(
                        "provider"
                    ),

                "media_id":
                    candidate.get(
                        "media_id"
                    ),

                "detected_countries":
                    sorted(
                        detected
                    ),

                "title":
                    candidate.get(
                        "title",
                        "",
                    ),
            })

            continue


        kept.append(
            candidate
        )


    # Safety:
    # never destroy an entire candidate pool.
    # The visual AI still receives project location
    # and can judge the remaining conflict.
    bypassed = False


    if (
        candidates
        and
        not kept
    ):

        kept = candidates

        bypassed = True


    return (
        kept,
        rejected,
        bypassed,
    )
