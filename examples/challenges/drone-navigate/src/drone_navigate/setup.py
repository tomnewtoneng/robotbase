from setuptools import setup

package_name = "drone_navigate"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Robotbase",
    maintainer_email="robotbase@users.noreply.github.com",
    description="Warehouse bot controller (starter).",
    license="MIT",
    entry_points={
        "console_scripts": [
            "controller = drone_navigate.controller:main",
        ],
    },
)
