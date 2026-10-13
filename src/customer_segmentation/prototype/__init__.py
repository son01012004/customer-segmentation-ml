"""Prototype-layer packages for DEV-03 (and future prototype DEVs).

This namespace separates *prototype-layer* implementations from the
*research core*. The research core ships under
``customer_segmentation.preprocessing``, ``.aggregation``,
``.features``, ``.transformation``, ``.clustering``, etc. — all
READ-ONLY for prototype DEVs.

The prototype layer is **optional**: it does not change any
research evidence, does not modify any research methodology, and
does not introduce new feature definitions or new algorithm
choices. It wraps the research core's public APIs and writes its
artefacts under ``data/prototype/<dataset_id>/`` (git-ignored).

Modules
-------
preprocessing     - DEV-03 Stage A→E (Dataset, Validation, Cleaning,
                    Transformation, Scaling); wraps FE-02 building blocks.
feature_generation - DEV-03 Stage F (Feature Generation: aggregation +
                    RFM/behavioral/cancellation); wraps FE-04 + FE-05.

Architecture
------------
- ADR-0005 Option A: offline, single-machine, file-based.
- No backend / API / database / worker / queue.
- Storage root fixed in ``configs/dev03_preprocessing.yaml``.
"""
