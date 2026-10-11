import json
from pathlib import Path

from pipeline.scene_pipeline import ScenePipeline


class BatchPipeline:

    def __init__(
        self,
        manifest_path,
        download_dir,
        review_mode="safe",
        resume=True,
        per_query=5,
        max_candidates=20,
        visual_top_n=5
    ):

        self.manifest_path = Path(
            manifest_path
        )

        self.download_dir = Path(
            download_dir
        )

        self.review_mode = review_mode
        self.resume = resume

        self.scene_pipeline = ScenePipeline(
            download_dir=self.download_dir,
            per_query=per_query,
            max_candidates=max_candidates,
            visual_top_n=visual_top_n,
            review_mode=review_mode
        )


    # ==================================================
    # LOAD MANIFEST
    # ==================================================

    def load_manifest(self):

        if not self.manifest_path.exists():

            raise FileNotFoundError(
                f"Manifest not found: "
                f"{self.manifest_path}"
            )

        with open(
            self.manifest_path,
            "r",
            encoding="utf-8"
        ) as file:

            manifest = json.load(file)

        if not manifest.get("scenes"):

            raise RuntimeError(
                "Manifest contains no scenes."
            )

        return manifest


    # ==================================================
    # SAVE MANIFEST
    # ==================================================

    def save_manifest(
        self,
        manifest
    ):

        with open(
            self.manifest_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                manifest,
                file,
                indent=4,
                ensure_ascii=False
            )


    # ==================================================
    # CHECK WHETHER SCENE CAN BE SKIPPED
    # ==================================================

    def should_skip(
        self,
        scene
    ):

        if not self.resume:
            return False

        stock = scene.get(
            "stock",
            {}
        )

        status = stock.get(
            "status"
        )

        # A validated scene has already completed
        # the stock pipeline successfully.
        if status == "validated":

            validation = stock.get(
                "validation",
                {}
            )

            download = stock.get(
                "download",
                {}
            )

            file_path = download.get(
                "path"
            )

            valid = validation.get(
                "valid"
            )

            # Do not blindly skip if the file
            # disappeared from disk.
            if (
                valid is True
                and file_path
                and Path(file_path).exists()
            ):
                return True

        return False


    # ==================================================
    # RUN BATCH
    # ==================================================

    def run(self):

        manifest = self.load_manifest()

        scenes = manifest[
            "scenes"
        ]

        total = len(scenes)

        summary = {
            "total": total,
            "validated": 0,
            "skipped": 0,
            "needs_review": 0,
            "search_again": 0,
            "failed": 0,
            "results": []
        }

        print("=" * 70)
        print("AI VIDEO EDITOR")
        print("BATCH SCENE PIPELINE")
        print("=" * 70)

        print(
            "Scenes:",
            total
        )

        print(
            "Review mode:",
            self.review_mode
        )

        print(
            "Resume:",
            self.resume
        )

        # ==========================================
        # PROCESS SCENES
        # ==========================================

        for index, scene in enumerate(
            scenes,
            start=1
        ):

            scene_id = scene.get(
                "scene_id",
                f"scene_{index:03d}"
            )

            print()
            print("#" * 70)

            print(
                f"SCENE {index}/{total}: "
                f"{scene_id}"
            )

            print("#" * 70)

            # ======================================
            # RESUME / SKIP
            # ======================================

            if self.should_skip(
                scene
            ):

                print(
                    "Already validated. "
                    "Skipping."
                )

                summary[
                    "skipped"
                ] += 1

                summary[
                    "validated"
                ] += 1

                summary[
                    "results"
                ].append({

                    "scene_id": scene_id,

                    "success": True,

                    "status": "validated",

                    "skipped": True
                })

                continue

            # ======================================
            # RUN SCENE
            # ======================================

            try:

                result = (
                    self.scene_pipeline.run(
                        scene
                    )
                )

            except Exception as error:

                # Save error into scene so that
                # one bad scene does not destroy
                # the entire batch.

                stock = scene.setdefault(
                    "stock",
                    {}
                )

                stock[
                    "status"
                ] = "pipeline_failed"

                stock[
                    "pipeline_error"
                ] = str(error)

                result = {
                    "success": False,
                    "scene_id": scene_id,
                    "status": "pipeline_failed",
                    "reason": str(error)
                }

                print()
                print(
                    "PIPELINE ERROR:",
                    error
                )

            # ======================================
            # SAVE AFTER EVERY SCENE
            # ======================================

            self.save_manifest(
                manifest
            )

            # ======================================
            # SUMMARY
            # ======================================

            status = result.get(
                "status",
                "unknown"
            )

            if status == "validated":

                summary[
                    "validated"
                ] += 1

            elif status == "needs_review":

                summary[
                    "needs_review"
                ] += 1

            elif status == "search_again":

                summary[
                    "search_again"
                ] += 1

            else:

                summary[
                    "failed"
                ] += 1

            summary[
                "results"
            ].append({

                "scene_id": scene_id,

                "success": result.get(
                    "success",
                    False
                ),

                "status": status,

                "skipped": False
            })

            print()
            print(
                "Progress saved:",
                self.manifest_path
            )

        # ==========================================
        # FINAL SAVE
        # ==========================================

        self.save_manifest(
            manifest
        )

        # ==========================================
        # SUMMARY
        # ==========================================

        print()
        print("=" * 70)
        print("BATCH COMPLETE")
        print("=" * 70)

        print(
            "Total scenes:",
            summary["total"]
        )

        print(
            "Validated:",
            summary["validated"]
        )

        print(
            "Skipped:",
            summary["skipped"]
        )

        print(
            "Needs review:",
            summary["needs_review"]
        )

        print(
            "Search again:",
            summary["search_again"]
        )

        print(
            "Failed:",
            summary["failed"]
        )

        print()
        print(
            "Manifest:",
            self.manifest_path
        )

        return summary