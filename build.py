#!/usr/bin/env python3
"""
Kalico Firmware Build System
Builds Kalico firmware for multiple targets with permutations
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class KalicoBuilder:
    S3_BUCKET = "kalico-flasher"
    CLOUDFRONT_DISTRIBUTION_ID = "E12YCK1HLQNF8F"

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.index_template_file = self.root_dir / "index-template.json"
        self.index_file = self.root_dir / "index.json"
        self.kconfigs_dir = self.root_dir / "kconfigs"
        self.builds_dir = self.root_dir / "builds"

    def load_index_template(self) -> dict[str, Any]:
        """Load the index-template.json file"""
        with open(self.index_template_file) as f:
            return json.load(f)

    def load_index(self) -> dict[str, Any]:
        """Load or generate index.json from template"""
        if not self.index_file.exists():
            # Generate from template if doesn't exist
            template = self.load_index_template()
            self.save_index(template)

        with open(self.index_file) as f:
            return json.load(f)

    def save_index(self, data: dict[str, Any]):
        """Save the index.json file"""
        with open(self.index_file, "w") as f:
            json.dump(data, f, indent=4)
            f.write("\n")

    def generate_permutations(self, target: dict[str, Any]) -> list[dict[str, str]]:
        """Generate all permutation combinations for a target"""
        config = target.get("configuration", {})
        permutations = config.get("permutations", {})

        if not permutations:
            return [{}]

        # Get all permutation keys and their values
        keys = list(permutations.keys())
        values = [permutations[key] for key in keys]

        # Generate all combinations
        combinations = []
        for combo in product(*values):
            combinations.append(dict(zip(keys, combo, strict=True)))

        return combinations

    def format_filename(self, template: str, target: dict[str, Any], permutation: dict[str, str]) -> str:
        """Format a filename using the template and permutation values"""
        params = {
            "targetId": target.get("targetId"),
            "vendorId": target.get("vendorId"),
            **permutation,
        }
        return template.format(**params)

    def _get_template(self, config: dict[str, Any], primary_key: str, fallback_key: str, default: str) -> str:
        """Get template from config with fallback support"""
        return config.get(primary_key) or config.get(fallback_key) or default

    def get_kconfig_filename(self, target: dict[str, Any], permutation: dict[str, str]) -> str:
        """Get the kconfig filename for a target and permutation"""
        config = target.get("configuration", {})
        template = self._get_template(
            config,
            "kconfigFilenameTemplate",
            "kconfigTemplate",
            "{targetId}_{vendorId}.kconfig",
        )
        return self.format_filename(template, target, permutation)

    def get_firmware_filename(self, target: dict[str, Any], permutation: dict[str, str]) -> str:
        """Get the firmware filename for a target and permutation"""
        config = target.get("configuration", {})
        template = self._get_template(
            config,
            "firmwareFilenameTemplate",
            "fileTemplate",
            "{targetId}_{vendorId}.bin",
        )
        return self.format_filename(template, target, permutation)

    def compile_kalico(
        self,
        kconfig_path: Path,
        output_path: Path,
        kalico_dir: Path,
        dry_run: bool = False,
    ) -> bool:
        """Compile Kalico firmware with a given kconfig"""
        try:
            if not dry_run:
                shutil.copy(kconfig_path, kalico_dir / ".config")
                subprocess.run(["make", "clean"], cwd=kalico_dir, check=True, capture_output=True)
                subprocess.run(
                    ["make", "-j", str(os.cpu_count() or 1)],
                    cwd=kalico_dir,
                    check=True,
                    capture_output=True,
                )

                # Try possible firmware output names
                for firmware_name in ["klipper.bin", "klipper.elf"]:
                    firmware_source = kalico_dir / "out" / firmware_name
                    if firmware_source.exists():
                        shutil.copy(firmware_source, output_path)
                        print(f"  ✓ {output_path.name}")
                        return True

                print(f"  ✗ {output_path.name} - no output found")
                return False

            print(f"  [DRY RUN] {output_path.name}")
            return True

        except subprocess.CalledProcessError:
            print(f"  ✗ {output_path.name} - build failed")
            return False
        except Exception as e:
            print(f"  ✗ {output_path.name} - {e}")
            return False

    def build(self, version: str, kalico_dir: str, commit_url: str = "", dry_run: bool = False):
        """Build all firmware targets"""
        kalico_path = Path(kalico_dir).resolve()

        if not dry_run and not kalico_path.exists():
            print("Error: Kalico directory not found")
            sys.exit(1)

        index = self.load_index()

        version_dir = self.builds_dir / version
        version_dir.mkdir(parents=True, exist_ok=True)

        # Track metadata
        metadata = {"targets": []}

        targets = index.get("targets", [])
        total_builds = 0
        successful_builds = 0

        for target in targets:
            target_id = target.get("targetId")
            print(f"\n[{target_id}]")

            permutations = self.generate_permutations(target)

            # Add target to metadata in TargetReleaseBundle shape
            metadata["targets"].append(self._create_target_metadata(target))

            for permutation in permutations:
                total_builds += 1

                # Get filenames
                kconfig_filename = self.get_kconfig_filename(target, permutation)
                firmware_filename = self.get_firmware_filename(target, permutation)

                kconfig_path = self.kconfigs_dir / kconfig_filename
                firmware_path = version_dir / firmware_filename

                if not kconfig_path.exists():
                    print(f"  ⚠ {kconfig_filename} - not found")
                    continue

                # Compile
                if self.compile_kalico(kconfig_path, firmware_path, kalico_path, dry_run):
                    successful_builds += 1

        # Save metadata
        metadata_path = version_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=4)
            f.write("\n")

        print(f"\nBuild: {successful_builds}/{total_builds} successful → {version_dir}")

        # Update index.json builds array
        if not dry_run:
            self.update_build_in_index(version, commit_url)

    def _create_target_metadata(self, target: dict[str, Any]) -> dict[str, Any]:
        """Create normalized target metadata for TargetReleaseBundle"""
        config = target.get("configuration", {})
        return {
            "targetId": target.get("targetId"),
            "vendorId": target.get("vendorId"),
            "configuration": {
                "firmwareFilenameTemplate": config.get("firmwareFilenameTemplate") or config.get("fileTemplate"),
                "kconfigFilenameTemplate": config.get("kconfigFilenameTemplate") or config.get("kconfigTemplate"),
                "permutations": config.get("permutations", {}),
            },
        }

    def _create_build_entry(self, version: str, commit_url: str = "") -> dict[str, Any]:
        """Create a build entry with current timestamp"""
        return {
            "version": version,
            "buildDate": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "githubCommitUrl": commit_url,
        }

    def update_build_in_index(self, version: str, commit_url: str = ""):
        """Add or update a build entry in index.json"""
        index = self.load_index()
        builds = index.get("builds", [])
        build_entry = self._create_build_entry(version, commit_url)

        # Find and update existing entry or append new one
        for i, build in enumerate(builds):
            if build.get("version") == version:
                builds[i] = build_entry
                break
        else:
            builds.append(build_entry)

        # Sort builds by version (newest first)
        builds.sort(key=lambda x: x.get("version", ""), reverse=True)
        index["builds"] = builds
        self.save_index(index)

    def rebuild_index(self):
        """Rebuild index.json from template and builds/ directory"""
        if not self.builds_dir.exists():
            print("Error: builds/ not found")
            sys.exit(1)

        # Load template and existing builds
        index = self.load_index_template()
        existing_builds = self.load_index().get("builds", []) if self.index_file.exists() else []
        by_version = {b.get("version"): b for b in existing_builds if isinstance(b, dict)}

        versions: list[dict[str, Any]] = [
            by_version.get(entry.name, self._create_build_entry(entry.name))
            for entry in self.builds_dir.iterdir()
            if entry.is_dir()
        ]

        versions.sort(key=lambda x: x.get("version", ""), reverse=True)
        index["builds"] = versions
        self.save_index(index)
        print(f"✓ Rebuilt index with {len(versions)} builds")

    def check_configurations(self):
        """Check for permutation values used in targets but missing from configurations catalog"""

        index = self.load_index()
        targets = index.get("targets", [])
        configurations = index.get("configurations", [])

        # Build a set of all permutation IDs defined in configurations
        defined_ids = {perm.get("id") for config in configurations for perm in config.get("permutations", [])}

        # Collect all unique permutation values used across all targets
        used_values = {
            value
            for target in targets
            for values in target.get("configuration", {}).get("permutations", {}).values()
            for value in values
        }

        missing_ids = used_values - defined_ids

        if missing_ids:
            print(f"Missing {len(missing_ids)} configuration displayNames:")
            for missing_id in sorted(missing_ids):
                print(f"  - {missing_id}")
            sys.exit(1)
        else:
            print(f"✓ All {len(used_values)} permutation values have displayNames")

    def validate_kconfigs(self):
        """Validate that all required kconfig files exist"""

        index = self.load_index()
        targets = index.get("targets", [])

        missing_files = []
        existing_files = []
        total_configs = 0

        for target in targets:
            permutations = self.generate_permutations(target)

            for permutation in permutations:
                total_configs += 1
                kconfig_filename = self.get_kconfig_filename(target, permutation)
                kconfig_path = self.kconfigs_dir / kconfig_filename

                if kconfig_path.exists():
                    existing_files.append(kconfig_filename)
                else:
                    missing_files.append(kconfig_filename)

        pct = len(existing_files) * 100 // total_configs if total_configs > 0 else 0

        if missing_files:
            print(f"Missing {len(missing_files)}/{total_configs} kconfig files ({pct}% complete):")
            for filename in missing_files[:10]:  # Show first 10
                print(f"  - {filename}")
            if len(missing_files) > 10:
                print(f"  ... and {len(missing_files) - 10} more")
            sys.exit(1)
        else:
            print(f"✓ All {total_configs} kconfig files present")

    def sync_to_s3(self, dry_run: bool = False):
        """Sync index.json and builds/ directory to S3 bucket"""
        try:
            s3_client = boto3.client("s3")
            s3_client.head_bucket(Bucket=self.S3_BUCKET)

            uploaded_count = 0
            total_size = 0

            # Upload index.json
            if self.index_file.exists():
                file_size = self.index_file.stat().st_size
                if not dry_run:
                    s3_client.upload_file(
                        str(self.index_file),
                        self.S3_BUCKET,
                        "index.json",
                        ExtraArgs={"ContentType": "application/json"},
                    )
                uploaded_count += 1
                total_size += file_size

            # Upload builds/ directory
            if self.builds_dir.exists():
                for file_path in self.builds_dir.rglob("*"):
                    if file_path.is_file():
                        s3_key = str(file_path.relative_to(self.root_dir)).replace("\\", "/")
                        file_size = file_path.stat().st_size

                        if not dry_run:
                            s3_client.upload_file(
                                str(file_path),
                                self.S3_BUCKET,
                                s3_key,
                                ExtraArgs={"ContentType": self._get_content_type(file_path)},
                            )

                        uploaded_count += 1
                        total_size += file_size

            # Summary
            action = "Would upload" if dry_run else "Uploaded"
            print(f"{action} {uploaded_count} files ({self._format_size(total_size)}) to s3://{self.S3_BUCKET}/")

            # Invalidate CloudFront
            if not dry_run and self.CLOUDFRONT_DISTRIBUTION_ID:
                self._invalidate_cloudfront()

        except NoCredentialsError:
            print("Error: AWS credentials not configured")
            sys.exit(1)
        except ClientError as e:
            print(f"Error: {e}")
            sys.exit(1)

    def _get_content_type(self, file_path: Path) -> str:
        """Determine content type based on file extension"""
        suffix = file_path.suffix.lower()
        content_types = {
            ".json": "application/json",
            ".bin": "application/octet-stream",
            ".elf": "application/octet-stream",
            ".uf2": "application/octet-stream",
            ".hex": "application/octet-stream",
        }
        return content_types.get(suffix, "application/octet-stream")

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _invalidate_cloudfront(self):
        """Invalidate CloudFront cache"""
        try:
            cloudfront = boto3.client("cloudfront")
            response = cloudfront.create_invalidation(
                DistributionId=self.CLOUDFRONT_DISTRIBUTION_ID,
                InvalidationBatch={
                    "Paths": {"Quantity": 1, "Items": ["/*"]},
                    "CallerReference": f"sync-{datetime.now(UTC).isoformat()}",
                },
            )
            print(f"CloudFront invalidation: {response['Invalidation']['Id']}")
        except Exception as e:
            print(f"Warning: CloudFront invalidation failed - {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Kalico Firmware Build System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check for missing configuration displayNames
  %(prog)s check-configurations

  # Validate all required kconfig files exist
  %(prog)s validate

  # Build all firmware for version v0.12.0-124
  %(prog)s build v0.12.0-124 --kalico-dir ../kalico

  # Dry run (echo commands only)
  %(prog)s build v0.12.0-124 --kalico-dir ../kalico --dry-run

  # Rebuild the builds index
  %(prog)s rebuild-index

  # Sync to S3 bucket
  %(prog)s sync

  # Sync dry run (show what would be uploaded)
  %(prog)s sync --dry-run
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build firmware for all targets")
    build_parser.add_argument("version", help="Version string (e.g., v0.12.0-124)")
    build_parser.add_argument("--kalico-dir", required=True, help="Path to Kalico source directory")
    build_parser.add_argument(
        "--commit-url",
        default="",
        help="GitHub commit URL for this build (e.g., https://github.com/KalicoCrew/kalico/commit/abc123)",
    )
    build_parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them")
    build_parser.add_argument("--root-dir", default=".", help="Root directory (default: current directory)")

    # Check-configurations command
    check_config_parser = subparsers.add_parser(
        "check-configurations", help="Check for missing configuration displayNames"
    )
    check_config_parser.add_argument("--root-dir", default=".", help="Root directory (default: current directory)")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate all required kconfig files exist")
    validate_parser.add_argument("--root-dir", default=".", help="Root directory (default: current directory)")

    # Rebuild-index command
    rebuild_parser = subparsers.add_parser("rebuild-index", help="Rebuild builds array in index.json")
    rebuild_parser.add_argument("--root-dir", default=".", help="Root directory (default: current directory)")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Sync index.json and builds/ to S3 bucket")
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without actually uploading",
    )
    sync_parser.add_argument("--root-dir", default=".", help="Root directory (default: current directory)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    builder = KalicoBuilder(args.root_dir)

    if args.command == "build":
        builder.build(args.version, args.kalico_dir, args.commit_url, args.dry_run)
    elif args.command == "check-configurations":
        builder.check_configurations()
    elif args.command == "validate":
        builder.validate_kconfigs()
    elif args.command == "rebuild-index":
        builder.rebuild_index()
    elif args.command == "sync":
        builder.sync_to_s3(getattr(args, "dry_run", False))


if __name__ == "__main__":
    main()
