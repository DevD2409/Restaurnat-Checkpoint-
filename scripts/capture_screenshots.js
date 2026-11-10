import puppeteer from 'puppeteer-core';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const BASE_URL = 'http://127.0.0.1:5173';

const viewports = {
  mobile_375: { width: 375, height: 812, isMobile: true, hasTouch: true },
  mobile_430: { width: 430, height: 932, isMobile: true, hasTouch: true },
  tablet_768: { width: 768, height: 1024, isMobile: false },
  desktop_1366: { width: 1366, height: 768, isMobile: false },
  desktop_1920: { width: 1920, height: 1080, isMobile: false },
};

const pagesToCapture = [
  { name: '01_customer_menu', path: '/menu' },
  { name: '02_customer_cart', path: '/menu/cart' },
  { name: '03_customer_tracking', path: '/menu/track/1' },
  { name: '04_customer_split_bill', path: '/menu/split-bill' },
  { name: '05_customer_wifi', path: '/menu/wifi' },
  { name: '06_customer_reserve', path: '/menu/reserve' },
  { name: '07_kitchen_display', path: '/kitchen' },
  { name: '08_waiter_dashboard', path: '/staff' },
  { name: '09_admin_overview', path: '/admin/overview' },
  { name: '10_admin_analytics', path: '/admin/analytics' },
  { name: '11_admin_menu', path: '/admin/menu' },
  { name: '12_admin_tables_floormap', path: '/admin/tables' },
  { name: '13_admin_billing', path: '/admin/billing' },
  { name: '14_admin_staff', path: '/admin/staff' },
  { name: '15_admin_reservations', path: '/admin/reservations' },
  { name: '16_admin_settings', path: '/admin/settings' },
  { name: '17_auth_login', path: '/login' },
];

async function run(folder = 'before') {
  const outDir = path.join(__dirname, '..', 'screenshots', folder);
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  console.log(`Starting screenshot capture into: ${outDir}`);

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
  });

  const page = await browser.newPage();

  // Pre-seed localStorage with admin auth token so admin/staff pages render full data
  // Admin credentials: role ADMIN
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle2' });
  await page.evaluate(() => {
    localStorage.setItem(
      'srmp_auth_token',
      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwicm9sZSI6IkFETUlOIiwiZXhwIjoxODAwMDAwMDAwfQ.mock_signature'
    );
    localStorage.setItem(
      'srmp_auth_user',
      JSON.stringify({
        id: 1,
        username: 'admin',
        full_name: 'System Administrator',
        role: 'ADMIN',
        is_active: true,
      })
    );
    // Table session mock for customer pages
    localStorage.setItem('srmp_table_id', '1');
    localStorage.setItem('srmp_table_number', 'T-01');
  });

  // Capture selected key pages across key viewports
  for (const item of pagesToCapture) {
    console.log(`Capturing ${item.name} at ${item.path}...`);

    // Standard desktop (1366)
    await page.setViewport(viewports.desktop_1366);
    try {
      await page.goto(`${BASE_URL}${item.path}`, { waitUntil: 'load', timeout: 30000 });
      await new Promise((r) => setTimeout(r, 1200));
      const desktopFile = path.join(outDir, `${item.name}_desktop_1366.png`);
      await page.screenshot({ path: desktopFile, fullPage: false });
    } catch (err) {
      console.warn(`Failed desktop capture for ${item.name}: ${err.message}`);
    }

    // Mobile (375)
    await page.setViewport(viewports.mobile_375);
    try {
      await page.goto(`${BASE_URL}${item.path}`, { waitUntil: 'load', timeout: 30000 });
      await new Promise((r) => setTimeout(r, 1200));
      const mobileFile = path.join(outDir, `${item.name}_mobile_375.png`);
      await page.screenshot({ path: mobileFile, fullPage: false });
    } catch (err) {
      console.warn(`Failed mobile capture for ${item.name}: ${err.message}`);
    }
  }

  // Also capture a few at tablet (768) and large desktop (1920) for responsive records
  const responsiveSamples = [
    { name: '01_customer_menu', path: '/menu' },
    { name: '07_kitchen_display', path: '/kitchen' },
    { name: '08_waiter_dashboard', path: '/staff' },
    { name: '09_admin_overview', path: '/admin/overview' },
    { name: '12_admin_tables_floormap', path: '/admin/tables' },
  ];

  for (const item of responsiveSamples) {
    // 768 tablet
    await page.setViewport(viewports.tablet_768);
    await page.goto(`${BASE_URL}${item.path}`, { waitUntil: 'load', timeout: 30000 });
    await new Promise((r) => setTimeout(r, 1000));
    await page.screenshot({ path: path.join(outDir, `${item.name}_tablet_768.png`) });

    // 1920 large desktop
    await page.setViewport(viewports.desktop_1920);
    await page.goto(`${BASE_URL}${item.path}`, { waitUntil: 'load', timeout: 30000 });
    await new Promise((r) => setTimeout(r, 1000));
    await page.screenshot({ path: path.join(outDir, `${item.name}_desktop_1920.png`) });
  }

  await browser.close();
  console.log(`Successfully completed screenshot capture for ${folder}!`);
}

const targetFolder = process.argv[2] || 'before';
run(targetFolder).catch(console.error);
