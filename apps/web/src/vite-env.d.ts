interface ImportMetaEnv {
  /** Set to "false" for production builds to hide the development-only sign-in form. */
  readonly VITE_DEV_LOGIN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
