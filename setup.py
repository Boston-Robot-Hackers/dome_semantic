from setuptools import find_packages, setup

package_name = "dome_semantic"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="pitosalas",
    maintainer_email="pitosalas@gmail.com",
    description="Semantic map (confirmed object tracking) for the DOME robot.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "semantic_map_node = dome_semantic.semantic_map_node:main",
        ],
    },
)
