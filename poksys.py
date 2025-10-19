import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import datetime
import json
import os
import smtplib
from email.message import EmailMessage
import secure_cred  # soubor s přihlašovacími údaji pro SMTP

# ------------------- HELPERS -------------------
def validate_email(email):
    import re
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def send_receipt_email_txt(to_email, subject, body, txt_filename, smtp_server, smtp_port, smtp_user, smtp_pass):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = smtp_user
    msg['To'] = to_email
    msg.set_content(body)
    with open(txt_filename, "rb") as f:
        msg.add_attachment(f.read(), maintype="text", subtype="plain", filename=os.path.basename(txt_filename))
    with smtplib.SMTP_SSL(smtp_server, smtp_port) as smtp:
        smtp.login(smtp_user, smtp_pass)
        smtp.send_message(msg)

# ------------------- DATA MANAGERS -------------------
class ProductManager:
    def __init__(self):
        self.products = []

    def add_product(self, name, price):
        for p in self.products:
            if p.get("name") == name:
                p["price"] = round(price, 2)
                return
        self.products.append({"name": name, "price": round(price, 2)})

class SalesManager:
    def __init__(self):
        self.sales_history = []

    def record_sale(self, items, order_id, date, receipt_txt, payment_type, discount):
        items_copy = [{"name": i.get("name"), "price": float(i.get("price",0)), "count": int(i.get("count",1))} for i in items]
        self.sales_history.append({
            "order_id": order_id,
            "date": date,
            "items": items_copy,
            "receipt_txt": receipt_txt,
            "payment_type": payment_type,
            "discount": discount
        })

# ------------------- GUI FORMS -------------------
class EntryForm(tk.Toplevel):
    def __init__(self, parent, title, fields, defaults=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x260")
        self.grab_set()
        self.result = None
        self.vars = {}
        defaults = defaults or {}

        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)
        for field in fields:
            var = tk.StringVar(value=str(defaults.get(field, "")))
            self.vars[field] = var
            ttk.Label(container, text=field + ":").pack(anchor="w", pady=(5,0))
            ttk.Entry(container, textvariable=var).pack(fill="x")

        ttk.Button(container, text="Uložit", command=self.save).pack(pady=10)

    def save(self):
        self.result = {k: v.get() for k, v in self.vars.items()}
        self.destroy()

# ------------------- RECEIPT TEMPLATE -------------------
DEFAULT_RECEIPT_FORMAT = {
    "header": "="*50,
    "company_info": "{company_name}\n{company_address}\nTelefon: {company_tel}\nEmail: {company_email}",
    "order_info": "Číslo objednávky: {cislo_objednavky}\nDatum: {datum}\nPočet položek: {pocet_polozek}\nPlatba: {payment_type}\nSleva: {discount} %",
    "items_header": "Název".ljust(20) + "Ks".rjust(5) + "Cena".rjust(10) + "Celkem".rjust(12),
    "items": "{tabulka_polozek}",
    "total": "CELKEM K ÚHRADĚ: {celkem} CZK",
    "footer": "{company_footer}\nVytištěno: {cas_tisku}",
    "items_align": "left"
}

# ------------------- MAIN APPLICATION -------------------
class PokladniSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("Pokladní Systém")
        self.root.geometry("1100x650")
        self.product_manager = ProductManager()
        self.sales_manager = SalesManager()
        self.shopping_list = []
        self.receipt_format = DEFAULT_RECEIPT_FORMAT.copy()
        self.company_info = {
            "name": "Pokladní Systém",
            "address": "Praha, Česká republika",
            "tel": "+420 123 456 789",
            "email": "info@pokladni-system.cz",
            "footer": "Děkujeme za váš nákup!"
        }
        self.last_order_id = None
        self.load_data()
        self.login_screen()
        self.root.bind("<F4>", lambda e: self.complete_order())

    # ------------------- LOGIN -------------------
    def login_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        frame = ttk.Frame(self.root, padding=40)
        frame.pack(expand=True)
        ttk.Label(frame, text="Přihlášení", font=("Arial", 20, "bold")).pack(pady=20)
        ttk.Label(frame, text="Uživatelské jméno:").pack()
        username_entry = ttk.Entry(frame)
        username_entry.pack()
        ttk.Label(frame, text="Heslo:").pack()
        password_entry = ttk.Entry(frame, show="*")
        password_entry.pack()

        def check_login():
            if username_entry.get() == "uzivatel" and password_entry.get() == "poksys1":
                self.main_screen()
            else:
                messagebox.showerror("Chyba", "Nesprávné přihlašovací údaje!")

        ttk.Button(frame, text="Přihlásit se", command=check_login).pack(pady=10)

    # ------------------- MAIN SCREEN -------------------
    def main_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        frame_left = ttk.Frame(self.root, padding=10)
        frame_left.grid(row=0, column=0, sticky="nsew")
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        ttk.Label(frame_left, text="Produkty", font=("Arial", 14)).pack(pady=5)
        self.products_frame = ttk.Frame(frame_left)
        self.products_frame.pack(fill="both", expand=True)
        self.update_product_buttons()
        ttk.Button(frame_left, text="Přidat produkt", command=self.add_product_dialog).pack(pady=2, fill="x")
        ttk.Button(frame_left, text="Exportovat produkty", command=self.export_products).pack(pady=2, fill="x")
        ttk.Button(frame_left, text="Importovat produkty", command=self.import_products).pack(pady=2, fill="x")
        ttk.Button(frame_left, text="Nastavit firemní údaje", command=self.set_company_info).pack(pady=2, fill="x")

        frame_right = ttk.Frame(self.root, padding=10)
        frame_right.grid(row=0, column=1, sticky="nsew")

        ttk.Label(frame_right, text="Seznam nákupů", font=("Arial", 14)).pack()
        self.tree = ttk.Treeview(frame_right, columns=("Název","Ks","Cena"), show="headings", height=15)
        self.tree.heading("Název", text="Název produktu")
        self.tree.heading("Ks", text="Ks")
        self.tree.heading("Cena", text="Cena (CZK)")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.edit_shopping_item)

        self.total_label = ttk.Label(frame_right, text="Celkem: 0.00 CZK", font=("Arial", 12,"bold"))
        self.total_label.pack(pady=5)

        btn_frame = ttk.Frame(frame_right)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Zakončit účet (F4)", command=self.complete_order).grid(row=0,column=0,padx=5)
        ttk.Button(btn_frame, text="Reset", command=self.reset_system).grid(row=0,column=1,padx=5)
        ttk.Button(btn_frame, text="Historie prodeje", command=self.show_history).grid(row=0,column=2,padx=5)
        ttk.Button(btn_frame, text="Nastavit formát účtenky", command=self.set_receipt_format).grid(row=0,column=3,padx=5)

        self.update_shopping_list()

    # ------------------- PRODUCTS -------------------
    def update_product_buttons(self):
        for widget in self.products_frame.winfo_children():
            widget.destroy()
        for product in self.product_manager.products:
            frame = ttk.Frame(self.products_frame)
            frame.pack(fill="x", pady=2)
            btn_add = ttk.Button(frame, text=f"{product.get('name')}\n{product.get('price')} CZK",
                                 command=lambda p=product: self.add_to_shopping_list(p))
            btn_add.pack(side="left", fill="x", expand=True)
            btn_plus1 = ttk.Button(frame, text="+1", width=3,
                                   command=lambda p=product: self.quick_add(p))
            btn_plus1.pack(side="left", padx=2)

    def add_product_dialog(self):
        form = EntryForm(self.root,"Přidat produkt",["Název","Cena"])
        self.root.wait_window(form)
        if form.result:
            name = form.result["Název"].strip()
            try:
                price = float(form.result["Cena"])
                if price<=0: raise ValueError
            except ValueError:
                messagebox.showerror("Chyba","Neplatná cena!")
                return
            self.product_manager.add_product(name, price)
            self.save_data()
            self.update_product_buttons()

    # ------------------- SHOPPING LIST -------------------
    def add_to_shopping_list(self, product, count=None):
        if count is None:
            count_str = simpledialog.askstring("Počet kusů", f"Zadejte počet kusů produktu '{product.get('name')}':")
            try:
                count=int(count_str)
                if count<=0: raise ValueError
            except (TypeError,ValueError):
                messagebox.showerror("Chyba","Neplatný počet kusů!")
                return
        self.shopping_list.append({"name":product.get("name"),"price":float(product.get("price",0)),"count":count})
        self.update_shopping_list()

    def quick_add(self,product):
        for item in self.shopping_list:
            if item.get("name")==product.get("name"):
                item["count"]+=1
                self.update_shopping_list()
                return
        self.add_to_shopping_list(product,1)

    def update_shopping_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        total=0
        for item in self.shopping_list:
            count=int(item.get("count",1))
            price=float(item.get("price",0))
            celk_item=price*count
            self.tree.insert("", "end", values=(item.get("name"), count, f"{celk_item:.2f}"))
            total+=celk_item
        self.total_label.config(text=f"Celkem: {total:.2f} CZK")

    def edit_shopping_item(self,event):
        selected=self.tree.focus()
        if not selected: return
        idx = self.tree.index(selected)
        item=self.shopping_list[idx]
        new_count = simpledialog.askinteger("Upravit počet","Zadejte nový počet kusů", initialvalue=int(item.get("count",1)))
        if new_count is None or new_count<=0: return
        self.shopping_list[idx]["count"]=new_count
        self.update_shopping_list()

    # ------------------- COMPLETE ORDER -------------------
    def complete_order(self):
        if not self.shopping_list:
            messagebox.showinfo("Info","Nákupní seznam je prázdný.")
            return

        # platba a sleva
        payment_type = simpledialog.askstring("Platba","Zadejte typ platby (Hotově/Kartou/Převodem):", initialvalue="Hotově")
        if not payment_type: payment_type="Hotově"
        discount = simpledialog.askfloat("Sleva","Zadejte slevu (%)", initialvalue=0.0)
        if discount is None: discount=0.0

        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        order_id = f"OBJ-{int(datetime.datetime.now().timestamp()*1000)}"
        self.last_order_id=order_id

        receipt_txt = self.create_receipt_txt_content(order_id, now, payment_type, discount)
        txt_filename="receipt.txt"
        with open(txt_filename,"w",encoding="utf-8") as f:
            f.write(receipt_txt)

        # Uložit do historie
        self.sales_manager.record_sale(self.shopping_list,order_id,now,receipt_txt,payment_type,discount)
        self.save_data()

        # Přehled okno
        self.show_order_summary(order_id, receipt_txt)

        self.shopping_list.clear()
        self.update_shopping_list()
        messagebox.showinfo("Hotovo","Nákup byl uložen do historie a vymazán.\nÚčtenka byla vygenerována.")

    # ------------------- RECEIPT -------------------
    def create_receipt_txt_content(self, order_id, datum, payment_type, discount):
        pocet_polozek = sum([item['count'] for item in self.shopping_list])
        celkem = sum([item['price']*item['count'] for item in self.shopping_list])*(1-discount/100)
        tabulka=""
        for item in self.shopping_list:
            celk_item=item['price']*item['count']
            tabulka+=f"{item['name']}\t{item['count']}\t{item['price']:.2f} CZK\t{celk_item:.2f} CZK\n"

        company_info = self.receipt_format["company_info"].format(
            company_name=self.company_info["name"],
            company_address=self.company_info["address"],
            company_tel=self.company_info["tel"],
            company_email=self.company_info["email"]
        )
        order_info = self.receipt_format["order_info"].format(
            cislo_objednavky=order_id,
            datum=datum,
            pocet_polozek=pocet_polozek,
            payment_type=payment_type,
            discount=discount
        )
        items_header = self.receipt_format["items_header"]
        items = self.receipt_format["items"].format(tabulka_polozek=tabulka)
        total = self.receipt_format["total"].format(celkem=f"{celkem:.2f}")
        footer = self.receipt_format["footer"].format(
            company_footer=self.company_info["footer"],
            cas_tisku=datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        )
        return f"{self.receipt_format['header']}\n{company_info}\n{order_info}\n{items_header}\n{items}\n{total}\n{footer}"

    # ------------------- ORDER SUMMARY -------------------
    def show_order_summary(self, order_id, receipt_txt):
        win=tk.Toplevel(self.root)
        win.title(f"Shrnutí objednávky {order_id}")
        win.geometry("600x400")
        text=tk.Text(win)
        text.insert("1.0", receipt_txt)
        text.pack(fill="both",expand=True)
        ttk.Button(win,text="Zavřít",command=win.destroy).pack(pady=5)

    # ------------------- SETTINGS -------------------
    def set_receipt_format(self):
        form = EntryForm(self.root,"Nastavení šablony účtenky",list(DEFAULT_RECEIPT_FORMAT.keys()),self.receipt_format)
        self.root.wait_window(form)
        if form.result:
            self.receipt_format.update(form.result)
            self.save_data()
            messagebox.showinfo("Info","Šablona účtenky byla uložena.")

    def set_company_info(self):
        form = EntryForm(self.root,"Firemní údaje",["name","address","tel","email","footer"],self.company_info)
        self.root.wait_window(form)
        if form.result:
            self.company_info.update(form.result)
            self.save_data()
            messagebox.showinfo("Info","Firemní údaje byly uloženy.")

    # ------------------- HISTORY -------------------
    def show_history(self):
        win=tk.Toplevel(self.root)
        win.title("Historie prodeje")
        win.geometry("700x400")
        tree=ttk.Treeview(win,columns=("Objednávka","Datum","Platba","Sleva","Celkem"),show="headings")
        tree.heading("Objednávka",text="Objednávka")
        tree.heading("Datum",text="Datum")
        tree.heading("Platba",text="Platba")
        tree.heading("Sleva",text="Sleva %")
        tree.heading("Celkem",text="Celkem CZK")
        tree.pack(fill="both",expand=True)

        for sale in self.sales_manager.sales_history:
            celkem=sum([i["price"]*i["count"] for i in sale["items"]])*(1-sale.get("discount",0)/100.0)
            tree.insert("", "end", values=(sale["order_id"], sale["date"], sale["payment_type"], sale.get("discount",0), f"{celkem:.2f}"))

        def show_receipt(event):
            sel=tree.focus()
            if not sel: return
            idx=tree.index(sel)
            receipt_txt=self.sales_manager.sales_history[idx]["receipt_txt"]
            self.show_order_summary(tree.item(sel)["values"][0], receipt_txt)

        tree.bind("<Double-1>",show_receipt)

    # ------------------- SYSTEM -------------------
    def reset_system(self):
        if messagebox.askyesno("Reset","Opravdu chcete resetovat systém?"):
            self.product_manager.products.clear()
            self.shopping_list.clear()
            self.sales_manager.sales_history.clear()
            self.save_data()
            self.update_product_buttons()
            self.update_shopping_list()

    def export_products(self):
        with open("products.json","w",encoding="utf-8") as f:
            json.dump(self.product_manager.products,f,ensure_ascii=False,indent=2)
        messagebox.showinfo("Export","Produkty byly exportovány do products.json.")

    def import_products(self):
        if os.path.exists("products.json"):
            with open("products.json","r",encoding="utf-8") as f:
                self.product_manager.products=json.load(f)
            self.save_data()
            self.update_product_buttons()
            messagebox.showinfo("Import","Produkty byly importovány.")
        else:
            messagebox.showerror("Chyba","Soubor products.json neexistuje.")

    # ------------------- DATA PERSISTENCE -------------------
    def save_data(self):
        data={
            "products": self.product_manager.products,
            "sales_history": self.sales_manager.sales_history,
            "receipt_format": self.receipt_format,
            "company_info": self.company_info
        }
        with open("pokladna_data.json","w",encoding="utf-8") as f:
            json.dump(data,f,ensure_ascii=False,indent=2)

    def load_data(self):
        if os.path.exists("pokladna_data.json"):
            try:
                with open("pokladna_data.json","r",encoding="utf-8") as f:
                    data=json.load(f)
                    self.product_manager.products=data.get("products",[])
                    self.sales_manager.sales_history=data.get("sales_history",[])
                    self.receipt_format=data.get("receipt_format",DEFAULT_RECEIPT_FORMAT.copy())
                    self.company_info=data.get("company_info",self.company_info)
            except (FileNotFoundError,json.JSONDecodeError):
                pass

# ------------------- RUN -------------------
if __name__=="__main__":
    root=tk.Tk()
    app=PokladniSystem(root)
    root.mainloop()
