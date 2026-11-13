use std::{
    env,
    ffi::OsString,
    fs,
    path::{Path, PathBuf},
    process::Command,
};

fn main() {
    println!("cargo:rerun-if-changed=assets/shutter.ico");
    println!("cargo:rerun-if-env-changed=RC");
    println!("cargo:rerun-if-env-changed=WINDRES");

    if env::var_os("CARGO_CFG_WINDOWS").is_none() {
        return;
    }

    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("Cargo manifest directory"));
    let out = PathBuf::from(env::var("OUT_DIR").expect("Cargo output directory"));
    let version = env::var("CARGO_PKG_VERSION").expect("Cargo package version");
    let numeric_version = numeric_version(&version);
    let msvc = env::var("CARGO_CFG_TARGET_ENV").is_ok_and(|value| value == "msvc");

    compile_resource(
        &manifest,
        &out,
        &version,
        &numeric_version,
        msvc,
        "kohdalab-shutter",
        "KohdaLab Shutter CLI",
    );

    // The GUI binary is disabled by `--no-default-features`; only ask rustc to
    // link its resource when Cargo is building that target.
    if env::var_os("CARGO_FEATURE_GUI").is_some() {
        compile_resource(
            &manifest,
            &out,
            &version,
            &numeric_version,
            msvc,
            "kohdalab-shutter-gui",
            "KohdaLab Shutter",
        );
    }
}

fn compile_resource(
    manifest: &Path,
    out: &Path,
    version: &str,
    numeric_version: &str,
    msvc: bool,
    name: &str,
    description: &str,
) {
    let icon = manifest
        .join("assets/shutter.ico")
        .display()
        .to_string()
        .replace('\\', "/");
    let rc = out.join(format!("{name}.rc"));
    fs::write(
        &rc,
        format!(
            r#"101 ICON "{icon}"
1 VERSIONINFO
FILEVERSION {numeric_version}
PRODUCTVERSION {numeric_version}
FILEFLAGSMASK 0x3fL
FILEFLAGS 0x0L
FILEOS 0x40004L
FILETYPE 0x1L
FILESUBTYPE 0x0L
BEGIN
 BLOCK "StringFileInfo"
 BEGIN
  BLOCK "040904B0"
  BEGIN
   VALUE "CompanyName", "Kohdalab\0"
   VALUE "FileDescription", "{description}\0"
   VALUE "FileVersion", "{version}\0"
   VALUE "InternalName", "{name}\0"
   VALUE "OriginalFilename", "{name}.exe\0"
   VALUE "ProductName", "KohdaLab Shutter\0"
   VALUE "ProductVersion", "{version}\0"
   VALUE "LegalCopyright", "Copyright KohdaLab contributors\0"
  END
 END
 BLOCK "VarFileInfo"
 BEGIN
  VALUE "Translation", 0x409, 1200
 END
END
"#
        ),
    )
    .expect("write Windows resource script");

    let resource = out.join(format!("{name}.{}", if msvc { "res" } else { "o" }));
    let status = if msvc {
        Command::new(msvc_rc())
            .arg("/nologo")
            .arg("/fo")
            .arg(&resource)
            .arg(&rc)
            .status()
    } else {
        let windres =
            env::var_os("WINDRES").unwrap_or_else(|| OsString::from("x86_64-w64-mingw32-windres"));
        Command::new(windres)
            .args(["-O", "coff", "-i"])
            .arg(&rc)
            .arg("-o")
            .arg(&resource)
            .status()
    }
    .expect("Windows resource compiler is required");
    assert!(status.success(), "Windows resource compiler failed");
    println!("cargo:rustc-link-arg-bin={name}={}", resource.display());
}

fn numeric_version(version: &str) -> String {
    let mut parts = version.split('-').next().unwrap_or(version).split('.');
    let major = parts.next().unwrap_or("0");
    let minor = parts.next().unwrap_or("0");
    let patch = parts.next().unwrap_or("0");
    format!("{major},{minor},{patch},0")
}

fn msvc_rc() -> OsString {
    if let Some(rc) = env::var_os("RC") {
        return rc;
    }

    let mut candidates = Vec::new();
    for root in [
        env::var_os("WindowsSdkVerBinPath"),
        env::var_os("ProgramFiles(x86)"),
    ]
    .into_iter()
    .flatten()
    {
        let root = PathBuf::from(root);
        let kits_bin = root.join("Windows Kits/10/bin");
        candidates.push(root.join("x64/rc.exe"));
        if let Ok(entries) = fs::read_dir(kits_bin) {
            for entry in entries.flatten() {
                candidates.push(entry.path().join("x64/rc.exe"));
            }
        }
    }
    candidates.sort();
    if let Some(path) = candidates.into_iter().rev().find(|path| path.is_file()) {
        return path.into_os_string();
    }
    OsString::from("rc.exe")
}
