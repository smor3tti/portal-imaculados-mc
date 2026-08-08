# Backup do banco

O plano gratuito do Supabase **não faz backup automático**. Com dados reais de
integrantes no ar — incluindo endereço e CNH — uma exclusão acidental seria
irreversível. Este procedimento cobre essa lacuna.

## Onde fica

O script `backup.ps1` está na **máquina do administrador**, em
`Desktop\Backup_Imaculados\`, junto de um `LEIA-ME.txt`.

Ele **não é versionado com os dados** de propósito: os arquivos gerados contêm
informação pessoal dos integrantes, e este repositório é público.

## Como funciona

1. Usa `pg_dump` para gerar um `.sql` completo (estrutura + dados)
2. Guarda a senha do banco codificada na pasta, atrelada ao usuário do Windows,
   para não pedir toda vez
3. Mantém os 12 backups mais recentes e apaga os antigos sozinho

## Frequência recomendada

**Mensal, depois de dar baixa nas mensalidades** — é quando há mais informação
nova a perder. Também antes de qualquer mudança grande no sistema.

## Alternativa sem instalar nada

Painel do Supabase → **Database → Backups → Download**.

## Regras sobre os arquivos gerados

Os `.sql` contêm nome, telefone, e-mail, data de nascimento e — para alguns —
endereço e número da CNH.

- Nunca subir para o GitHub
- Nunca enviar por WhatsApp ou e-mail
- Nunca guardar em pasta compartilhada com o clube
- Se for para nuvem, que seja conta pessoal do administrador

## Restauração

Restaurar por cima de um banco com dados pode gerar conflito. O caminho seguro é
criar um projeto novo no Supabase, restaurar lá, conferir, e só então apontar o
portal para ele.
