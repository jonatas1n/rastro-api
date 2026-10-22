"""Pacotes e fragmentos alinhados a `rastro/lib/services/bank_notification_sources.dart`.

SMS da Caixa fica de fora: autorizar o app de mensagens mandaria cada SMS para a IA.
"""
from __future__ import annotations

from sqlmodel import Session, select

from ..database import engine
from ..models.db import AppWhitelist

# (package_name ou fragmento, nome amigável)
_SEED: tuple[tuple[str, str], ...] = (
    ("br.com.bb.android", "Banco do Brasil"),
    ("com.bb.android", "Banco do Brasil"),
    ("bb.android", "Banco do Brasil"),
    ("com.itau", "Itaú"),
    ("com.itaucard", "Itaú"),
    ("br.com.itau", "Itaú"),
    ("itaucard", "Itaú"),
    (".itau.", "Itaú"),
    ("br.com.bradesco", "Bradesco"),
    ("bradesco", "Bradesco"),
    ("com.santander.app", "Santander"),
    ("br.com.santander", "Santander"),
    ("santander", "Santander"),
    ("br.com.caixa", "Caixa"),
    ("br.com.government.caixa", "Caixa"),
    ("br.gov.caixa.tem", "Caixa"),
    ("br.com.caixa.tem", "Caixa"),
    ("caixa.tem", "Caixa"),
    ("gov.caixa", "Caixa"),
    ("com.nu.production", "Nubank"),
    ("com.nu.production.debug", "Nubank"),
    ("nu.production", "Nubank"),
    ("br.com.intermedium", "Inter"),
    ("com.bancointer", "Inter"),
    ("intermedium", "Inter"),
    ("bancointer", "Inter"),
    ("br.com.c6bank.app", "C6 Bank"),
    ("c6bank", "C6 Bank"),
    ("com.pagbank", "PagBank"),
    ("br.com.uol.ps.myaccount", "PagBank"),
    ("pagbank", "PagBank"),
    ("ps.myaccount", "PagBank"),
    ("com.mercadopago.wallet", "Mercado Pago"),
    ("mercadopago", "Mercado Pago"),
    ("com.picpay", "PicPay"),
    ("picpay", "PicPay"),
    ("br.com.neon", "Neon"),
    ("br.com.itau.iti", "iti"),
    ("com.itau.iti", "iti"),
    (".iti", "iti"),
    ("com.next", "Next"),
    ("br.com.next", "Next"),
    ("com.original.bank", "Original"),
    ("br.com.original.bank", "Original"),
    ("original.bank", "Original"),
    ("br.com.bancobmg", "Banco BMG"),
    ("bancobmg", "Banco BMG"),
    ("br.com.bancopan", "Banco PAN"),
    ("bancopan", "Banco PAN"),
    ("br.com.agibank", "Agibank"),
    ("agibank", "Agibank"),
    ("br.com.btgpactual.digital", "BTG Pactual"),
    ("com.btgpactual.app", "BTG Pactual"),
    ("btgpactual", "BTG Pactual"),
    ("br.com.bs2", "Banco BS2"),
    ("br.com.mercantil", "Banco Mercantil"),
    ("br.com.bv", "Banco BV"),
    ("br.com.bancobv", "Banco BV"),
    ("bancobv", "Banco BV"),
    ("br.com.sicoob", "Sicoob"),
    ("sicoob", "Sicoob"),
    ("br.com.sicredi.app", "Sicredi"),
    ("br.com.sicredi", "Sicredi"),
    ("sicredi", "Sicredi"),
    ("com.pay99", "99Pay"),
    ("com.app99.pay", "99Pay"),
    ("99pay", "99Pay"),
    ("br.com.digimais", "Banco Digimais"),
    ("digimais", "Banco Digimais"),
    ("br.com.zrobank", "Zro Bank"),
    ("bank.zro", "Zro Bank"),
    ("zrobank", "Zro Bank"),
    ("zro.bank", "Zro Bank"),
    ("com.starkbank", "Stark Bank"),
    ("starkbank", "Stark Bank"),
    ("br.com.s3bank", "S3 Bank"),
    ("s3bank", "S3 Bank"),
    ("ng.cash.app", "NG.CASH"),
    ("com.ng.cash", "NG.CASH"),
    ("ng.cash", "NG.CASH"),
    ("de.number26.android", "N26"),
    ("number26", "N26"),
    ("br.com.bancodigio", "Banco Digio"),
    ("br.com.digio", "Banco Digio"),
    ("bancodigio", "Banco Digio"),
)


def seed_app_whitelist() -> None:
    """Insere pacotes que ainda não existem. Não reativa um app desligado."""
    with Session(engine) as session:
        existing = {
            row.package_name.lower()
            for row in session.exec(select(AppWhitelist)).all()
        }
        for package_name, display_name in _SEED:
            key = package_name.lower()
            if key in existing:
                continue
            session.add(
                AppWhitelist(
                    package_name=package_name,
                    display_name=display_name,
                    allowed=True,
                )
            )
            existing.add(key)
        session.commit()
