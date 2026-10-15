# ParaLate third-party notices

ParaLate includes and distributes third-party software. Each component remains
under its own license; this document does not replace any upstream license.
The release's `ThirdPartyLicenses` directory contains the full license texts
and a package/version inventory generated from the actual release environment.

## Important bundled components

| Component | License | Notes |
|---|---|---|
| PyQt6 | GPL-3.0 | Riverbank's commercial license is a separate option from the project license. |
| PyMuPDF / MuPDF | AGPL-3.0 or Artifex commercial license | The open-source distribution must meet AGPL-3.0 requirements. |
| Qt libraries | LGPL-3.0 and other component-specific licenses | See the bundled Qt license texts and upstream notices. |
| cryptography | Apache-2.0 or BSD-3-Clause | See the bundled notices. |
| requests | Apache-2.0 | See the bundled notices. |
| python-dotenv | BSD-3-Clause | See the bundled notices. |

The ParaLate application source is offered under GPL-3.0-only. The copyright
holder may separately offer a commercial license for ParaLate's own code;
that grant does not relicense or waive any third-party terms. In particular,
distribution of a closed-source build requires all necessary third-party
commercial permissions, including those for PyQt6 and PyMuPDF.

The `Source` directory contains the corresponding ParaLate source snapshot,
build configuration, dependency pins and upstream source locations for bundled
components. This release is not a substitute for obtaining legal advice about
the obligations that apply to a particular redistribution.
