/** Sitio 100 % estático: no hay código de servidor, solo habla con el cliente local (127.0.0.1). */
const nextConfig = {
  output: 'export',
  reactStrictMode: true,
  poweredByHeader: false,
};

export default nextConfig;
