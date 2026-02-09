import os
import json

import datetime

from fpm.utils import load_template, save_file, get_output_path


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
