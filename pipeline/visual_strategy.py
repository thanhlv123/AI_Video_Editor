import re

from pipeline.context_geo import (
    detect_countries,
)


# ==================================================
# GEO POLICIES
# ==================================================

STRICT = "STRICT"
REGIONAL_PROXY = "REGIONAL_PROXY"
VISUAL_PROXY = "VISUAL_PROXY"
GENERIC = "GENERIC"


# ==================================================
# VISUAL REGIONAL PROFILES
#
# These are retrieval-expansion profiles.
# They do NOT claim that countries are identical.
# ==================================================

REGIONAL_PROFILES = {

    "morocco": {
        "regions": [
            "North Africa",
            "Maghreb",
            "Mediterranean",
        ],

        "proxy_countries": [
            "algeria",
            "tunisia",
        ],

        "visual_terms": [
            "North African",
            "Maghreb",
            "Mediterranean",
            "warm dry climate",
            "arid landscape",
        ],
    },

    "serbia": {
        "regions": [
            "Balkans",
            "Southeast Europe",
            "Eastern Europe",
        ],

        "proxy_countries": [
            "bosnia and herzegovina",
            "montenegro",
            "north macedonia",
            "croatia",
            "bulgaria",
        ],

        "visual_terms": [
            "Balkan",
            "Southeast European",
            "continental European",
        ],
    },

    "vietnam": {
        "regions": [
            "Southeast Asia",
            "Tropical Asia",
        ],

        "proxy_countries": [
            "thailand",
            "laos",
            "cambodia",
            "malaysia",
            "indonesia",
        ],

        "visual_terms": [
            "Southeast Asian",
            "tropical rural",
            "humid tropical",
        ],
    },
}


# ==================================================
# KNOWN NAMED PLACES
# ==================================================

KNOWN_PLACES = {

    # Morocco
    "casablanca",
    "marrakech",
    "marrakesh",
    "rabat",
    "fes",
    "fez",
    "tangier",
    "agadir",
    "meknes",
    "essaouira",
    "chefchaouen",
    "atlas mountains",
    "strait of gibraltar",
    "sahara",

    # Serbia
    "belgrade",
    "beograd",
    "novi sad",

    # Common landmarks
    "eiffel tower",
    "times square",
    "burj khalifa",
    "mount fuji",
    "grand canyon",
    "big ben",
    "colosseum",
    "sydney opera house",
}


PHYSICAL_FEATURES = {

    "atlas mountains",
    "strait of gibraltar",
    "eiffel tower",
    "burj khalifa",
    "mount fuji",
    "grand canyon",
    "big ben",
    "colosseum",
    "sydney opera house",
}


# ==================================================
# PRIMARY VISUAL SIGNALS
# ==================================================

STRONG_REGIONAL_SUBJECT_TERMS = {

    "mountain community",
    "mountain village",
    "mountain landscape",

    "snowy mountain",
    "snow covered mountain",

    "ski resort",
    "skiing",

    "ancient landscape",
    "desert landscape",
    "coastal landscape",

    "north africa",
    "north african landscape",

    "ancestral homeland",
    "homeland landscape",

    "rural settlement",
    "mountain settlement",

    "desert",
    "mountains",
    "mountain",

    "coastline",
    "coastal",

    "valley",
    "forest",
    "ruins",
}


HUMAN_VISUAL_TERMS = {

    "young woman",
    "young women",

    "woman",
    "women",

    "young man",
    "young men",

    "student",
    "students",
    "university student",

    "family",
    "families",
    "multigenerational family",

    "farmer",
    "farmers",

    "worker",
    "workers",

    "street fashion",
    "modern clothing",
    "clothing",
    "fashion",

    "smartphone",
    "using phone",
    "social media",

    "family gathering",
    "wedding gathering",

    "daily life",
    "urban lifestyle",
}


VISUAL_OBJECT_TERMS = {

    "bride market",
    "market",

    "vineyard",
    "vineyards",

    "grapevine",
    "grapevines",

    "grape cultivation",
    "vineyard cultivation",

    "cultivation",
    "cultivated field",

    "grape harvest",

    "agriculture",
    "farming",

    "food",
    "coffee",

    "traffic",

    "street",

    "house",
    "home",
    "apartment",
}


STRICT_GEO_CUES = {

    "map",
    "geographic",
    "geography",

    "country overview",
    "border",

    "separated from",

    "strait",

    "aerial coastline",
    "location map",
}


# ==================================================
# BASIC HELPERS
# ==================================================

def _clean(value):

    return str(
        value
        or ""
    ).strip()


def _norm(value):

    return (
        _clean(value)
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )


def _contains_any(
    value,
    terms,
):

    source = _norm(
        value
    )

    return any(
        _norm(term) in source
        for term in terms
    )


def _dedupe(
    values,
):

    result = []
    seen = set()

    for value in values:

        value = re.sub(
            r"\s+",
            " ",
            _clean(value),
        ).strip()

        if not value:
            continue

        key = value.lower()

        if key in seen:
            continue

        seen.add(
            key
        )

        result.append(
            value
        )

    return result


# ==================================================
# FIND NAMED PLACE IN REAL DIALOGUE
#
# AI-generated keywords are deliberately ignored here.
# ==================================================

def find_dialogue_place(
    dialogue,
):

    source = _norm(
        dialogue
    )

    for place in sorted(
        KNOWN_PLACES,
        key=len,
        reverse=True,
    ):

        if place in source:

            return place

    return None


# ==================================================
# COUNTRY AS VISUAL SUBJECT
# ==================================================

def _country_is_main_subject(
    dialogue,
    analysis,
    country,
):

    if not country:
        return False

    dialogue_text = _norm(
        dialogue
    )

    country_text = _norm(
        country
    )

    if country_text not in dialogue_text:
        return False

    combined = " ".join(
        [
            dialogue_text,

            _norm(
                analysis.get(
                    "subject"
                )
            ),

            _norm(
                analysis.get(
                    "context"
                )
            ),
        ]
    )

    if _contains_any(
        combined,
        STRICT_GEO_CUES,
    ):

        return True

    if (
        "this is "
        + country_text
    ) in dialogue_text:

        return True

    return False


# ==================================================
# NAMED PLACE AS ACTUAL VISUAL SUBJECT
# ==================================================

def _named_place_is_main_subject(
    place,
    dialogue,
    analysis,
    primary_keyword,
):

    if not place:
        return False

    place_text = _norm(
        place
    )

    subject = _norm(
        analysis.get(
            "subject"
        )
    )

    context = _norm(
        analysis.get(
            "context"
        )
    )

    primary = _norm(
        primary_keyword
    )

    dialogue_text = _norm(
        dialogue
    )

    # ----------------------------------------------
    # HUMAN OVERRIDE
    #
    # "women in Casablanca"
    # Casablanca is context, not the visual subject.
    # ----------------------------------------------

    if _contains_any(
        subject
        + " "
        + primary,
        HUMAN_VISUAL_TERMS,
    ):

        return False

    # ----------------------------------------------
    # REAL PHYSICAL FEATURE
    # ----------------------------------------------

    if place_text in PHYSICAL_FEATURES:

        if (
            place_text in dialogue_text
            and
            (
                place_text in subject
                or
                place_text in primary
                or
                place_text in context
            )
        ):

            return True

    # ----------------------------------------------
    # City/location visually identifiable
    # ----------------------------------------------

    landscape_cues = {

        "skyline",
        "cityscape",
        "aerial",
        "panorama",
        "coastline",
        "landmark",
        "map",
    }

    if (
        place_text in subject
        or
        place_text in primary
    ):

        if _contains_any(
            subject
            + " "
            + primary,
            landscape_cues,
        ):

            return True

    return False


# ==================================================
# CLASSIFY ONE SCENE
# ==================================================

def classify_scene(
    scene,
):

    dialogue = _clean(
        scene.get(
            "dialogue"
        )
    )

    analysis = scene.get(
        "analysis",
        {},
    )

    search = scene.get(
        "search",
        {},
    )

    project_context = scene.get(
        "project_context",
        {},
    )

    country = _clean(
        project_context.get(
            "required_country"
        )
    )

    # Prefer original semantic keyword before
    # Context Carryover added the country prefix.
    primary_keyword = _clean(
        search.get(
            "original_primary_keyword"
        )
        or
        search.get(
            "primary_keyword"
        )
    )

    subject = _clean(
        analysis.get(
            "subject"
        )
    )

    action = _clean(
        analysis.get(
            "action"
        )
    )

    context = _clean(
        analysis.get(
            "context"
        )
    )

    location = _clean(
        analysis.get(
            "original_location"
        )
        or
        analysis.get(
            "location"
        )
    )

    explicit_place = (
        find_dialogue_place(
            dialogue
        )
    )

    # ==================================================
    # 1. COUNTRY ITSELF IS VISUAL SUBJECT
    # ==================================================

    if _country_is_main_subject(
        dialogue,
        analysis,
        country,
    ):

        return {
            "geo_policy":
                STRICT,

            "reason":
                (
                    "Project country itself is "
                    "the geographic visual subject."
                ),

            "explicit_place":
                country,

            "signal":
                "country_subject",
        }

    # ==================================================
    # 2. NAMED LANDMARK / FEATURE
    # ==================================================

    if _named_place_is_main_subject(
        explicit_place,
        dialogue,
        analysis,
        primary_keyword,
    ):

        return {
            "geo_policy":
                STRICT,

            "reason":
                (
                    "Specific named geographic feature "
                    "is the main visual subject."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "named_feature",
        }

    # ==================================================
    # PRIMARY VISUAL SIGNAL
    # ==================================================

    primary_visual = " ".join(
        [
            subject,
            primary_keyword,
        ]
    )

    # ==================================================
    # 3. ENVIRONMENT / REGIONAL SUBJECT
    # ==================================================

    if _contains_any(
        primary_visual,
        STRONG_REGIONAL_SUBJECT_TERMS,
    ):

        # Vineyard is an ordinary reusable
        # visual subject rather than a landmark.
        if _contains_any(
            primary_visual,
            {
                "vineyard",
                "grapevine",
                "grapevines",
                "grape cultivation",
            },
        ):

            return {
                "geo_policy":
                    VISUAL_PROXY,

                "reason":
                    (
                        "Vineyard/agricultural subject "
                        "can use compatible proxy footage."
                    ),

                "explicit_place":
                    explicit_place,

                "signal":
                    "visual_object",
            }

        return {
            "geo_policy":
                REGIONAL_PROXY,

            "reason":
                (
                    "Primary visual subject is "
                    "environmental/geographic, but "
                    "exact country is not mandatory."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "regional_subject",
        }

    # ==================================================
    # 4. HUMAN / LIFESTYLE
    # ==================================================

    if _contains_any(
        primary_visual,
        HUMAN_VISUAL_TERMS,
    ):

        return {
            "geo_policy":
                VISUAL_PROXY,

            "reason":
                (
                    "Primary visual subject is human "
                    "activity/lifestyle; location is "
                    "contextual."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "human_subject",
        }

    # ==================================================
    # 5. ORDINARY STOCK SUBJECT
    # ==================================================

    if _contains_any(
        primary_visual,
        VISUAL_OBJECT_TERMS,
    ):

        return {
            "geo_policy":
                VISUAL_PROXY,

            "reason":
                (
                    "Ordinary visual subject can use "
                    "compatible proxy footage."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "visual_object",
        }

    # ==================================================
    # SECONDARY SIGNAL
    # ==================================================

    secondary = " ".join(
        [
            action,
            context,
            location,
            dialogue,
        ]
    )

    if _contains_any(
        secondary,
        STRONG_REGIONAL_SUBJECT_TERMS,
    ):

        return {
            "geo_policy":
                REGIONAL_PROXY,

            "reason":
                (
                    "Scene carries strong regional "
                    "or environmental visual character."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "secondary_region",
        }

    if _contains_any(
        secondary,
        HUMAN_VISUAL_TERMS,
    ):

        return {
            "geo_policy":
                VISUAL_PROXY,

            "reason":
                (
                    "Human/lifestyle imagery is the "
                    "best available visual proxy."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "secondary_human",
        }

    if _contains_any(
        secondary,
        VISUAL_OBJECT_TERMS,
    ):

        return {
            "geo_policy":
                VISUAL_PROXY,

            "reason":
                (
                    "Ordinary subject can use "
                    "proxy footage."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "secondary_object",
        }

    if explicit_place:

        return {
            "geo_policy":
                REGIONAL_PROXY,

            "reason":
                (
                    "Named place is contextual rather "
                    "than a mandatory visible landmark."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "contextual_place",
        }

    return {
        "geo_policy":
            GENERIC,

        "reason":
            (
                "No mandatory geographic or regional "
                "visual requirement."
            ),

        "explicit_place":
            None,

        "signal":
            "generic",
    }


# ==================================================
# PROFILE
# ==================================================

def _get_profile(
    scene,
):

    project_context = scene.get(
        "project_context",
        {},
    )

    country_key = _norm(
        project_context.get(
            "required_country_key"
        )
    )

    return REGIONAL_PROFILES.get(
        country_key,
        {
            "regions": [],
            "proxy_countries": [],
            "visual_terms": [],
        },
    )


# ==================================================
# GENERICIZE QUERY
# ==================================================

def genericize_query(
    query,
    scene,
):

    result = _clean(
        query
    )

    project_context = scene.get(
        "project_context",
        {},
    )

    profile = _get_profile(
        scene
    )

    # VISUAL PROXY GENERICIZE 58D V2
    #
    # Proxy scenes should search by visible meaning,
    # not remain locked to an AI-inherited place name.
    remove_terms = [

        project_context.get(
            "required_country",
            ""
        ),

        *profile.get(
            "regions",
            []
        ),

        *KNOWN_PLACES,
    ]

    for term in sorted(
        remove_terms,
        key=lambda item: len(
            _clean(item)
        ),
        reverse=True,
    ):

        if not term:
            continue

        result = re.sub(
            re.escape(
                str(term)
            ),
            " ",
            result,
            flags=re.IGNORECASE,
        )

    return re.sub(
        r"\s+",
        " ",
        result,
    ).strip()


# ==================================================
# BUILD QUERY TIERS
# ==================================================

def build_query_tiers(
    scene,
    strategy,
):

    search = scene.get(
        "search",
        {},
    )

    project_context = scene.get(
        "project_context",
        {},
    )

    country = _clean(
        project_context.get(
            "required_country"
        )
    )

    profile = _get_profile(
        scene
    )

    current_primary = _clean(
        search.get(
            "primary_keyword"
        )
    )

    original_primary = _clean(
        search.get(
            "original_primary_keyword"
        )
        or
        current_primary
    )

    keywords = [

        _clean(item)

        for item
        in search.get(
            "keywords",
            []
        )

        if _clean(item)
    ]

    generic_primary = (
        genericize_query(
            original_primary,
            scene,
        )
        or
        original_primary
    )

    policy = strategy[
        "geo_policy"
    ]

    tiers = {
        "exact_geo": [],
        "regional_proxy": [],
        "visual_proxy": [],
        "generic": [],
    }

    # ==================================================
    # STRICT
    # ==================================================

    if policy == STRICT:

        tiers[
            "exact_geo"
        ] = _dedupe(
            [
                current_primary,
                *keywords[:4],
            ]
        )

        return tiers

    # ==================================================
    # OPTIONAL EXACT SEARCH
    # ==================================================

    if current_primary:

        tiers[
            "exact_geo"
        ].append(
            current_primary
        )

    # ==================================================
    # REGIONAL PROXY
    # ==================================================

    if policy == REGIONAL_PROXY:

        for region in (
            profile.get(
                "regions",
                []
            )[:3]
        ):

            tiers[
                "regional_proxy"
            ].append(
                f"{region} {generic_primary}"
            )

        for country_key in (
            profile.get(
                "proxy_countries",
                []
            )[:3]
        ):

            display = " ".join(
                word.capitalize()
                for word in country_key.split()
            )

            tiers[
                "regional_proxy"
            ].append(
                f"{display} {generic_primary}"
            )

        for visual_term in (
            profile.get(
                "visual_terms",
                []
            )[:3]
        ):

            tiers[
                "visual_proxy"
            ].append(
                f"{visual_term} {generic_primary}"
            )

        tiers[
            "generic"
        ].append(
            generic_primary
        )

    # ==================================================
    # VISUAL PROXY
    # ==================================================

    elif policy == VISUAL_PROXY:

        for region in (
            profile.get(
                "regions",
                []
            )[:2]
        ):

            tiers[
                "regional_proxy"
            ].append(
                f"{region} {generic_primary}"
            )

        for visual_term in (
            profile.get(
                "visual_terms",
                []
            )[:3]
        ):

            tiers[
                "visual_proxy"
            ].append(
                f"{visual_term} {generic_primary}"
            )

        tiers[
            "generic"
        ].append(
            generic_primary
        )

        for keyword in keywords[:3]:

            generic_keyword = (
                genericize_query(
                    keyword,
                    scene,
                )
            )

            if generic_keyword:

                tiers[
                    "generic"
                ].append(
                    generic_keyword
                )

    # ==================================================
    # GENERIC
    # ==================================================

    else:

        tiers[
            "generic"
        ].append(
            generic_primary
        )

        for keyword in keywords[:4]:

            generic_keyword = (
                genericize_query(
                    keyword,
                    scene,
                )
            )

            if generic_keyword:

                tiers[
                    "generic"
                ].append(
                    generic_keyword
                )

    for tier_name in tiers:

        tiers[
            tier_name
        ] = _dedupe(
            tiers[
                tier_name
            ]
        )

    return tiers


# ==================================================
# INTERLEAVE QUERY TIERS
#
# Prevent exact/regional searches from consuming
# the entire candidate quota before generic queries
# are reached.
# ==================================================

def interleave_query_tiers(
    tiers,
):

    exact = list(
        tiers.get(
            "exact_geo",
            []
        )
    )

    regional = list(
        tiers.get(
            "regional_proxy",
            []
        )
    )

    visual = list(
        tiers.get(
            "visual_proxy",
            []
        )
    )

    generic = list(
        tiers.get(
            "generic",
            []
        )
    )

    result = []

    # Prefer one exact query first.
    if exact:

        result.append(
            exact.pop(0)
        )

    while (
        exact
        or regional
        or visual
        or generic
    ):

        for bucket in (
            regional,
            visual,
            generic,
            exact,
        ):

            if bucket:

                result.append(
                    bucket.pop(0)
                )

    return _dedupe(
        result
    )


# ==================================================
# ATTACH VISUAL STRATEGY TO MANIFEST
#
# activate_search=False:
#   metadata only, current search behavior unchanged.
#
# activate_search=True:
#   rewrites search terms for multi-tier retrieval.
# ==================================================

def enrich_manifest_with_visual_strategy(
    manifest,
    activate_search=False,
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

    for scene in scenes:

        if scene.get(
            "scene_type"
        ) == "gap":

            continue

        strategy = classify_scene(
            scene
        )

        tiers = build_query_tiers(
            scene,
            strategy,
        )

        queries = interleave_query_tiers(
            tiers
        )

        profile = _get_profile(
            scene
        )

        visual_strategy = dict(
            strategy
        )

        visual_strategy[
            "query_tiers"
        ] = tiers

        visual_strategy[
            "search_queries"
        ] = queries

        visual_strategy[
            "proxy_countries"
        ] = list(
            profile.get(
                "proxy_countries",
                []
            )
        )

        visual_strategy[
            "regions"
        ] = list(
            profile.get(
                "regions",
                []
            )
        )

        scene[
            "visual_strategy"
        ] = visual_strategy

        # ----------------------------------------------
        # Metadata-only mode.
        # ----------------------------------------------

        if not activate_search:

            continue

        search = scene.setdefault(
            "search",
            {},
        )

        search[
            "pre_visual_strategy_primary_keyword"
        ] = search.get(
            "primary_keyword"
        )

        search[
            "pre_visual_strategy_keywords"
        ] = list(
            search.get(
                "keywords",
                []
            )
            or []
        )

        # STRICT keeps existing geo-targeted behavior.
        if (
            strategy[
                "geo_policy"
            ]
            == STRICT
        ):

            continue

        generic_queries = tiers.get(
            "generic",
            []
        )

        if generic_queries:

            ranking_primary = (
                generic_queries[0]
            )

        else:

            ranking_primary = (
                genericize_query(
                    search.get(
                        "original_primary_keyword"
                    )
                    or
                    search.get(
                        "primary_keyword"
                    ),
                    scene,
                )
            )

        ranking_primary = (
            ranking_primary
            or
            search.get(
                "primary_keyword",
                ""
            )
        )

        search[
            "primary_keyword"
        ] = ranking_primary

        search[
            "keywords"
        ] = [

            query

            for query in queries

            if (
                query.lower()
                !=
                ranking_primary.lower()
            )

        ][
            :12
        ]

        search[
            "visual_proxy_search"
        ] = True

    return manifest


# ==================================================
# IDENTIFY QUERY TIER
# ==================================================

def infer_query_tier(
    scene,
    query,
):

    query_key = _norm(
        query
    )

    if not query_key:

        return None

    strategy = scene.get(
        "visual_strategy",
        {},
    )

    tiers = strategy.get(
        "query_tiers",
        {},
    )

    for tier_name, values in tiers.items():

        for value in values:

            if _norm(
                value
            ) == query_key:

                return tier_name

    return None


# ==================================================
# ADAPTIVE GEOGRAPHY FILTER
#
# STRICT:
#   Preserve Geography Guard behavior.
#
# Proxy modes:
#   Do not hard-reject another country simply because
#   its metadata names that country.
#
# This allows visually suitable substitute footage.
# ==================================================

def filter_adaptive_geography_candidates(
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

    required_country = _norm(
        project_context.get(
            "required_country_key"
        )
    )

    strategy = scene.get(
        "visual_strategy",
        {},
    )

    policy = strategy.get(
        "geo_policy",
        STRICT,
    )

    proxy_countries = set(

        _norm(item)

        for item
        in strategy.get(
            "proxy_countries",
            []
        )

        if _norm(item)
    )

    kept = []
    rejected = []

    for candidate in candidates:

        item = dict(
            candidate
        )

        metadata_text = " ".join(
            [
                str(
                    item.get(
                        "title",
                        ""
                    )
                    or ""
                ),

                str(
                    item.get(
                        "source_url",
                        ""
                    )
                    or ""
                ),

                str(
                    item.get(
                        "page_url",
                        ""
                    )
                    or ""
                ),

                str(
                    item.get(
                        "photographer",
                        ""
                    )
                    or ""
                ),

                str(
                    item.get(
                        "author",
                        ""
                    )
                    or ""
                ),
            ]
        )

        detected = detect_countries(
            metadata_text
        )

        item[
            "detected_countries"
        ] = sorted(
            detected
        )

        tier = infer_query_tier(
            scene,
            item.get(
                "matched_query",
                ""
            ),
        )

        item[
            "matched_query_tier"
        ] = tier

        # ==================================================
        # ADAPTIVE CONFLICT
        # ==================================================

        geography_conflict = False


        if (
            detected
            and
            required_country
        ):

            # ----------------------------------------------
            # STRICT
            #
            # Exact geography remains mandatory.
            # ----------------------------------------------

            if policy == STRICT:

                geography_conflict = (
                    required_country
                    not in detected
                )


            # ----------------------------------------------
            # REGIONAL / VISUAL PROXY
            #
            # Explicitly named unrelated countries are
            # rejected.
            #
            # Project country and configured proxy countries
            # are allowed.
            # ----------------------------------------------

            elif policy in (
                REGIONAL_PROXY,
                VISUAL_PROXY,
            ):

                project_match = (
                    required_country
                    in detected
                )

                proxy_match = bool(
                    detected
                    &
                    proxy_countries
                )

                geography_conflict = not (
                    project_match
                    or
                    proxy_match
                )


            # ----------------------------------------------
            # GENERIC
            #
            # Geography is deliberately ignored.
            # ----------------------------------------------

            else:

                geography_conflict = False


        if geography_conflict:

            rejected.append(
                {
                    "provider":
                        item.get(
                            "provider"
                        ),

                    "media_id":
                        item.get(
                            "media_id"
                        ),

                    "detected_countries":
                        sorted(
                            detected
                        ),

                    "title":
                        item.get(
                            "title",
                            ""
                        ),

                    "reason":
                        "adaptive_geography_conflict",

                    "geo_policy":
                        policy,
                }
            )

            continue


        # ==================================================
        # GEO COMPATIBILITY METADATA
        #
        # Stored for future ranking.
        # V1 does NOT change MediaRanker weights yet.
        # ==================================================

        if not detected:

            geo_score = 0.75

        elif (
            required_country
            and
            required_country in detected
        ):

            geo_score = 1.0

        elif (
            detected
            &
            proxy_countries
        ):

            geo_score = 0.90

        elif policy == GENERIC:

            geo_score = 0.75

        else:

            geo_score = 0.50


        item[
            "geo_compatibility"
        ] = round(
            geo_score,
            3
        )

        kept.append(
            item
        )


    # ==================================================
    # SAFETY BYPASS
    #
    # Preserve old V1 safety philosophy.
    # ==================================================

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

