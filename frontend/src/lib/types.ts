export type Me = { username: string; organization: { id: number; name: string; slug: string } };

export type Client = {
  id: number;
  name: string;
  bank_account: number;
  short_name: string;
  name_yayoi: string | null;
  register_no: string | null;
  post_code: string | null;
  address1: string;
  address2: string | null;
  tel: string | null;
  email: string | null;
  slug: string | null;
};

export type ItemCode = {
  id: number;
  name: string;
  short_name: string;
  tax_rate: string | null;
  slug: string | null;
};

export type AccountItem = {
  id: number;
  company: number;
  item_code: number;
  invoice_date: string | null;
  payment_due: string | null;
  action_date: string | null;
  action_name: string | null;
  action_note: string | null;
  tax_rate: number;
  invoice_bt: number;
  invoice_tax: number;
  invoice_at: number;
  flag: boolean;
  slug: string | null;
  deleted_at: string | null;
  invoice_issued: boolean;
};

export type InvoiceCode = {
  id: number;
  account_item_slug: string;
  invoice_slug: string | null;
  client_id: number;
  client_name: string;
  payment_due: string | null;
  invoice_bt_ttl_0: number;
  invoice_bt_ttl: number;
  invoice_tax_ttl: number;
  invoice_at_ttl: number;
  invoice_bt_gttl: number;
  invoice_at_gttl: number;
  invoice_tax_flag: boolean;
  sent_at: string | null;
  amended: boolean;
  items: AccountItem[];
};
