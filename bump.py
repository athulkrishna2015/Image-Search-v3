from new_version import read_manifest_version, bump_version_string, update_version


def bump_version():
    try:
        current_version = read_manifest_version("addon")
    except Exception as exc:
        print(f"Error: {exc}")
        return

    try:
        new_version = bump_version_string(current_version)
    except Exception as exc:
        print(f"Error: {exc}")
        return

    print(f"Bumping version: {current_version} → {new_version}")

    try:
        update_version(new_version, "addon")
        print(f"✅ Successfully updated manifest.json to {new_version}")
    except Exception as exc:
        print(f"❌ Failed to update version: {exc}")


if __name__ == "__main__":
    bump_version()
