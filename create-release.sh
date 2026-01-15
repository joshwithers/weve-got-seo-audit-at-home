#!/bin/bash
# Script to create a distribution-ready release package

set -e

VERSION="0.2.0"
PACKAGE_NAME="seo-audit-engine"
RELEASE_NAME="${PACKAGE_NAME}-v${VERSION}"

echo "=== Creating Release: ${RELEASE_NAME} ==="
echo

# Clean up any previous builds
echo "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info/
rm -f ${RELEASE_NAME}.tar.gz ${RELEASE_NAME}.zip

# Clean up development artifacts
echo "Cleaning development artifacts..."
rm -rf venv/ __pycache__/ audit_engine/__pycache__/ audit_engine/checks/__pycache__/
rm -f *.db *.sqlite *.sqlite3
rm -f audit_report.json audit_issues.csv audit_pages.csv

# Create source distribution (optional, only if setuptools is available)
if command -v python3 &> /dev/null && python3 -c "import setuptools" 2>/dev/null; then
    echo "Creating source distribution..."
    python3 setup.py sdist 2>/dev/null || echo "Skipping Python sdist (optional)"
fi

# Create release directory
echo "Creating release package..."
mkdir -p "dist/${RELEASE_NAME}"

# Copy files
cp -r audit_engine/ "dist/${RELEASE_NAME}/"
cp requirements.txt setup.py install.sh README.md LICENSE CHANGELOG.md "dist/${RELEASE_NAME}/"
cp .gitignore "dist/${RELEASE_NAME}/"

# Create tarball
cd dist
tar -czf "${RELEASE_NAME}.tar.gz" "${RELEASE_NAME}/"
zip -r "${RELEASE_NAME}.zip" "${RELEASE_NAME}/"
cd ..

# Move archives to root
mv dist/${RELEASE_NAME}.tar.gz .
mv dist/${RELEASE_NAME}.zip .

# Calculate checksums
echo
echo "Calculating checksums..."
if command -v shasum &> /dev/null; then
    shasum -a 256 ${RELEASE_NAME}.tar.gz > ${RELEASE_NAME}.tar.gz.sha256
    shasum -a 256 ${RELEASE_NAME}.zip > ${RELEASE_NAME}.zip.sha256
elif command -v sha256sum &> /dev/null; then
    sha256sum ${RELEASE_NAME}.tar.gz > ${RELEASE_NAME}.tar.gz.sha256
    sha256sum ${RELEASE_NAME}.zip > ${RELEASE_NAME}.zip.sha256
fi

# Get file sizes
TAR_SIZE=$(du -h ${RELEASE_NAME}.tar.gz | cut -f1)
ZIP_SIZE=$(du -h ${RELEASE_NAME}.zip | cut -f1)

echo
echo "=== Release Created Successfully! ==="
echo
echo "Files created:"
echo "  - ${RELEASE_NAME}.tar.gz (${TAR_SIZE})"
echo "  - ${RELEASE_NAME}.zip (${ZIP_SIZE})"
echo "  - ${RELEASE_NAME}.tar.gz.sha256"
echo "  - ${RELEASE_NAME}.zip.sha256"
if [ -f "dist/${PACKAGE_NAME}-${VERSION}.tar.gz" ]; then
    echo "  - dist/${PACKAGE_NAME}-${VERSION}.tar.gz (Python source dist)"
fi
echo
echo "Ready to distribute!"
echo
echo "Next steps:"
echo "  1. Test the tarball: tar -xzf ${RELEASE_NAME}.tar.gz && cd ${RELEASE_NAME} && ./install.sh"
echo "  2. Upload to GitHub releases"
echo "  3. Optionally publish to PyPI: twine upload dist/${PACKAGE_NAME}-${VERSION}.tar.gz"
echo
