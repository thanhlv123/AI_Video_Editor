import hashlib
import json
from pathlib import Path


class BatchSceneAnalyzer:

    CACHE_VERSION = 1


    def __init__(
        self,
        analyzer,
        cache_dir
    ):

        self.analyzer = analyzer

        self.cache_dir = Path(
            cache_dir
        )

        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True
        )


    # ==================================================
    # ANALYZE ALL SCENES
    # ==================================================

    def analyze_all(
        self,
        scenes,
        use_cache=True
    ):

        results = []

        stats = {
            "total": len(scenes),
            "api_calls": 0,
            "cache_hits": 0,
            "failed": 0
        }


        for number, scene in enumerate(
            scenes,
            start=1
        ):

            print()
            print(
                f"[{number}/{len(scenes)}] "
                f"{scene.id}"
            )


            try:

                result = self.analyze_one(
                    scene,
                    use_cache=use_cache
                )


                results.append(
                    result["analysis"]
                )


                if result["source"] == "cache":

                    stats["cache_hits"] += 1

                    print(
                        "  Source: CACHE"
                    )


                else:

                    stats["api_calls"] += 1

                    print(
                        "  Source: API"
                    )


                print(
                    "  Keyword:",
                    result[
                        "analysis"
                    ].search.primary_keyword
                )


            except Exception as error:

                stats["failed"] += 1

                print(
                    "  FAILED:",
                    error
                )

                raise


        return results, stats


    # ==================================================
    # ANALYZE ONE SCENE
    # ==================================================

    def analyze_one(
        self,
        scene,
        use_cache=True
    ):

        cache_key = self._cache_key(
            scene
        )


        cache_path = (
            self.cache_dir
            / f"{cache_key}.json"
        )


        # ----------------------------------------------
        # CACHE HIT
        # ----------------------------------------------

        if (
            use_cache
            and cache_path.exists()
        ):

            cached = self._load_cache(
                cache_path
            )


            analysis = (
                self._restore_analysis(
                    scene,
                    cached["analysis"]
                )
            )


            return {
                "source": "cache",
                "analysis": analysis,
                "cache_path": str(
                    cache_path
                )
            }


        # ----------------------------------------------
        # CALL AI
        # ----------------------------------------------

        analysis = (
            self.analyzer.analyze(
                scene
            )
        )


        # ----------------------------------------------
        # SAVE CACHE
        # ----------------------------------------------

        cache_data = {

            "cache_version": (
                self.CACHE_VERSION
            ),

            "scene_id": scene.id,

            "scene_hash": cache_key,

            "source": {
                "start": scene.start,
                "end": scene.end,
                "duration": scene.duration,
                "text": scene.text
            },

            "analysis": (
                analysis.to_dict()
            )
        }


        with open(
            cache_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                cache_data,
                file,
                indent=4,
                ensure_ascii=False
            )


        return {
            "source": "api",
            "analysis": analysis,
            "cache_path": str(
                cache_path
            )
        }


    # ==================================================
    # CACHE KEY
    # ==================================================

    def _cache_key(
        self,
        scene
    ):

        provider = (
            self.analyzer
            .provider
            .__class__
            .__name__
        )


        model = getattr(
            self.analyzer.provider,
            "model",
            "unknown"
        )


        reasoning = getattr(
            self.analyzer.provider,
            "reasoning_effort",
            "unknown"
        )


        data = {

            "version": (
                self.CACHE_VERSION
            ),

            "provider": provider,

            "model": model,

            "reasoning": reasoning,

            "start": round(
                scene.start,
                3
            ),

            "end": round(
                scene.end,
                3
            ),

            "text": scene.text.strip()
        }


        serialized = json.dumps(
            data,
            sort_keys=True,
            ensure_ascii=False
        )


        return hashlib.sha256(
            serialized.encode(
                "utf-8"
            )
        ).hexdigest()


    # ==================================================
    # LOAD CACHE
    # ==================================================

    def _load_cache(
        self,
        cache_path
    ):

        with open(
            cache_path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(
                file
            )


    # ==================================================
    # RESTORE SCENE ANALYSIS OBJECT
    # ==================================================

    def _restore_analysis(
        self,
        scene,
        data
    ):

        from ai.scene_schema import (
            SceneAnalysis,
            SceneContentAnalysis,
            SceneSearchData,
            SceneMediaData
        )


        analysis_data = data[
            "analysis"
        ]

        search_data = data[
            "search"
        ]

        media_data = data[
            "media"
        ]


        result = SceneAnalysis(

            scene_id=scene.id,

            start=scene.start,

            end=scene.end,

            duration=scene.duration,

            dialogue=scene.text,


            analysis=SceneContentAnalysis(

                context=analysis_data[
                    "context"
                ],

                subject=analysis_data[
                    "subject"
                ],

                action=analysis_data[
                    "action"
                ],

                location=analysis_data[
                    "location"
                ],

                mood=analysis_data[
                    "mood"
                ],

                shot=analysis_data[
                    "shot"
                ],

                motion=analysis_data[
                    "motion"
                ]
            ),


            search=SceneSearchData(

                primary_keyword=(
                    search_data[
                        "primary_keyword"
                    ]
                ),

                keywords=search_data.get(
                    "keywords",
                    []
                ),

                avoid=search_data.get(
                    "avoid",
                    []
                )
            ),


            media=SceneMediaData(

                preferred_type=(
                    media_data.get(
                        "preferred_type",
                        "video"
                    )
                ),

                selected=media_data.get(
                    "selected"
                )
            )
        )


        self.analyzer.validator.validate(
            result
        )


        return result