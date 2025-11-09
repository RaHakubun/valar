model_4, clip_4, vae_4 = checkpoint_loader_simple(ckpt_name="""dreamshaper_8.safetensors""")
image_5 = empty_latent_image(batch_size=1, height=512, width=512)
conditioning_6 = clip_text_encode(clip=clip_4, text="""a photo of a cat wearing a spacesuit inside a spaceship

high resolution, detailed, 4k""")
conditioning_7 = clip_text_encode(clip=clip_4, text="""blurry, illustration""")
latent_3 = k_sampler(cfg=7, denoise=1, latent_image=image_5, model=model_4, negative=conditioning_7, positive=conditioning_6, sampler_name="""dpmpp_2m""", scheduler="""karras""", seed=636250194499614, steps=20)
image_8 = vae_decode(samples=latent_3, vae=vae_4)
_ = save_image(filename_prefix="""ComfyUI""", images=image_8)
