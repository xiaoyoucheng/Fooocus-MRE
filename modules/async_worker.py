import threading
import json


buffer = []
outputs = []


def worker():
    global buffer, outputs

    import time
    import shared
    import random
    import modules.default_pipeline as pipeline
    import modules.path
    import modules.patch
    import fooocus_version

    from modules.sdxl_styles import apply_style, aspect_ratios
    from modules.private_logger import log

    try:
        async_gradio_app = shared.gradio_root
        flag = f'''App started successful. Use the app with {str(async_gradio_app.local_url)} or {str(async_gradio_app.server_name)}:{str(async_gradio_app.server_port)}'''
        if async_gradio_app.share:
            flag += f''' or {async_gradio_app.share_url}'''
        print(flag)
    except Exception as e:
        print(e)

    def handler(task):
        prompt, negative_prompt, style_selection, performance_selection, \
        aspect_ratios_selection, image_number, image_seed, sharpness, sampler_name, scheduler, \
        sampler_steps_speed, switch_step_speed, sampler_steps_quality, switch_step_quality, cfg, \
        base_model_name, refiner_model_name, base_clip_skip, refiner_clip_skip, \
        l1, w1, l2, w2, l3, w3, l4, w4, l5, w5, save_metadata_json, save_metadata_png = task

        loras = [(l1, w1), (l2, w2), (l3, w3), (l4, w4), (l5, w5)]

        modules.patch.sharpness = sharpness

        pipeline.refresh_base_model(base_model_name)
        pipeline.refresh_refiner_model(refiner_model_name)
        pipeline.refresh_loras(loras)
        pipeline.clean_prompt_cond_caches()

        p_txt, n_txt = apply_style(style_selection, prompt, negative_prompt)

        if performance_selection == 'Speed':
            steps = sampler_steps_speed
            switch = round(sampler_steps_speed * switch_step_speed)
        else:
            steps = sampler_steps_quality
            switch = round(sampler_steps_quality * switch_step_quality)

        width, height = aspect_ratios[aspect_ratios_selection]

        results = []
        metadata_strings = []

        seed = image_seed
        max_seed = 2**63 - 1
        if not isinstance(seed, int):
            seed = random.randint(0, max_seed)
        if seed < 0:
            seed = - seed
        seed = seed % max_seed

        all_steps = steps * image_number

        def callback(step, x0, x, total_steps, y):
            done_steps = i * steps + step
            outputs.append(['preview', (
                int(100.0 * float(done_steps) / float(all_steps)),
                f'Step {step}/{total_steps} in the {i}-th Sampling',
                y)])

        for i in range(image_number):
            imgs = pipeline.process(p_txt, n_txt, steps, switch, width, height, seed, sampler_name, scheduler, cfg, base_clip_skip, refiner_clip_skip, callback=callback)

            metadata = {
                'prompt': prompt, 'negative_prompt': negative_prompt, 'style': style_selection,
                'seed': seed, 'width': width, 'height': height, 'p_txt': p_txt, 'n_txt': n_txt,
                'sampler': sampler_name, 'scheduler': scheduler, 'performance': performance_selection,
                'steps': steps, 'switch': switch, 'sharpness': sharpness, 'cfg': cfg,
                'base_clip_skip': base_clip_skip, 'refiner_clip_skip': refiner_clip_skip,
                'base_model': base_model_name, 'refiner_model': refiner_model_name,
                'l1': l1, 'w1': w1, 'l2': l2, 'w2': w2, 'l3': l3, 'w3': w3,
                'l4': l4, 'w4': w4, 'l5': l5, 'w5': w5,
                'software': fooocus_version.full_version
            }
            metadata_string = json.dumps(metadata, ensure_ascii=False)
            metadata_strings.append(metadata_string)

            for x in imgs:
                d = [
                    ('Prompt', prompt),
                    ('Negative Prompt', negative_prompt),
                    ('Style', style_selection),
                    ('Seed', seed),
                    ('Resolution', str((width, height))),
                    ('Performance', performance_selection),
                    ('Sampler & Scheduler & Steps', str((sampler_name, scheduler, steps, switch))),
                    ('Sharpness', sharpness),
                    ('CFG & CLIP Skips', str((cfg, base_clip_skip, refiner_clip_skip))),
                    ('Base Model', base_model_name),
                    ('Refiner Model', refiner_model_name),
                ]
                for n, w in loras:
                    if n != 'None':
                        d.append((f'LoRA [{n}] weight', w))
                d.append(('Software', fooocus_version.full_version))
                log(x, d, metadata_string, save_metadata_json, save_metadata_png)

            seed += 1
            results += imgs

        outputs.append(['results', results])
        outputs.append(['metadatas', metadata_strings])
        return

    while True:
        time.sleep(0.01)
        if len(buffer) > 0:
            task = buffer.pop(0)
            handler(task)
    pass


threading.Thread(target=worker, daemon=True).start()
