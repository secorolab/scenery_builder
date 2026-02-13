import os
import json
import glob
import datetime
import logging

from fpm.utils import load_template, save_file, get_output_path
from robofair.metadata import FileMetadata

logger = logging.getLogger("floorplan.generators.prov")


def fpm_prov_generation_graph(model, model_path, generated_files, base_path, **kwargs):
    output_path = get_output_path(base_path, "prov")
    file_name = os.path.join(output_path, f"{model.name}.prov.json")

    gen_time = datetime.datetime.now().isoformat()
    template = load_template("prov/fpm-file-generation.json.jinja")
    prefix = os.path.commonprefix(generated_files)
    generated_files = [os.path.relpath(f, prefix) for f in generated_files]

    model_file = os.path.basename(model_path)

    contents = template.render(
        source_files=[model_file],
        generated_files=generated_files,
        gen_time=gen_time,
        env_id=f"{model.name}",
        model_base_iri=kwargs.get("model_base_iri"),
    )
    contents = json.loads(contents)
    return save_file(output_path, file_name, contents)


def jsonld_prov_metadata(fpm_file, generated_files, **kwargs):
    fpm_file_metadata(fpm_file)
    for f in generated_files:
        gen_file_metadata(f, [fpm_file])


def artefact_prov_generation_graph(
    env_id, source_files, generated_files, artefact_type, base_path, **kwargs
):
    gen_time = datetime.datetime.now().isoformat()

    generated_files = [os.path.relpath(f, base_path) for f in generated_files]
    source_files = [os.path.relpath(f, base_path) for f in source_files]

    output_path = get_output_path(base_path, "prov")
    file_name = os.path.join(output_path, f"{env_id}-{artefact_type.lower()}.prov.json")

    template = load_template("prov/artefact-file-generation.json.jinja")
    contents = template.render(
        source_files=source_files,
        generated_files=generated_files,
        gen_time=gen_time,
        env_id=env_id,
        artefact_type=artefact_type,
        model_base_iri=kwargs.get("model_base_iri"),
    )
    contents = json.loads(contents)
    return save_file(output_path, file_name, contents)


def artefact_prov_metadata(source_files, generated_files, **kwargs):
    _source_files = []
    for d in source_files:
        _source_files.extend(glob.glob(os.path.join(d, "*.json")))

    for f in generated_files:
        if os.path.basename(os.path.basename(f)) in kwargs.get(
            "ignored_extensions", []
        ):
            logger.debug(f"Skipping {f} metadata")
            continue

        gen_file_metadata(f, _source_files)


def gen_file_metadata(f, source_files):
    f_mdata = FileMetadata(f)
    mdata = dict(
        created_at=f_mdata.missing_metadata.get("updated_at"),
        attributed_to="https://purl.org/secorolab/scenery_builder",
        derived_from=[os.path.relpath(sf, os.path.dirname(f)) for sf in source_files],
    )
    f_mdata.add_missing_metadata(mdata, save=True)


def fpm_file_metadata(fpm_file):
    fpm_mdata = FileMetadata(fpm_file)
    if fpm_mdata.metadata_file is None:
        fpm_mdata.save_missing_metadata()


def var_prov_metadata(var_file, fpm_file, generated_files, **kwargs):
    for f in generated_files:
        gen_file_metadata(f, [var_file])

    fpm_file_metadata(fpm_file)

    var_mdata = FileMetadata(var_file)
    var_ref_fpm = {"references": os.path.relpath(fpm_file, os.path.dirname(var_file))}
    var_mdata.add_missing_metadata(var_ref_fpm, save=True)


def var_prov_generation_graph(var_file, fpm_file, generated_files, base_path, **kwargs):
    gen_time = datetime.datetime.now().isoformat()
    template = load_template("prov/var-file-generation.json.jinja")

    all_files = [f for f in generated_files]
    all_files.append(fpm_file)
    all_files.append(var_file)
    all_files.append(base_path)
    prefix = os.path.commonprefix(all_files)
    generated_files = [os.path.relpath(f, prefix) for f in generated_files]

    for gen_file in generated_files:
        file_name = f"{gen_file}.prov.json"
        contents = template.render(
            var_file=os.path.relpath(var_file, prefix),
            gen_file=gen_file,
            gen_time=gen_time,
            fpm_file=os.path.relpath(fpm_file, prefix),
            env_id="test",
            model_base_iri=kwargs.get("model_base_iri"),
        )
        contents = json.loads(contents)
        save_file(base_path, file_name, contents)
