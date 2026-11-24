import path from "node:path";

export const defaultBrandJson = (remotionProjectDir) => path.resolve(remotionProjectDir, "../../mailinfra-brand/brand.json");

export const brandAlias = (remotionProjectDir) => (config) => {
  const brandDir = process.env.REEL_BRAND;
  if (!brandDir) {
    return config;
  }
  return {
    ...config,
    resolve: {
      ...config.resolve,
      alias: {
        ...(config.resolve?.alias ?? {}),
        [defaultBrandJson(remotionProjectDir)]: path.resolve(brandDir, "brand.json"),
      },
    },
  };
};
