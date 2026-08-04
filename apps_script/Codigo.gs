/**
 * Portal Imaculados M.C. — API sobre Google Planilhas
 * =====================================================
 * Este script transforma uma planilha do Google no "banco de dados" do portal,
 * sem precisar contratar servidor. Ele publica um endereço web que o site
 * (GitHub Pages) consome.
 *
 * COMO INSTALAR (passo a passo no README desta pasta):
 *   1. Abra sua planilha  →  Extensões  →  Apps Script
 *   2. Apague o conteúdo e cole este arquivo inteiro
 *   3. Execute a função `prepararPlanilha` uma vez (cria as abas e o 1º acesso)
 *   4. Implantar → Nova implantação → Tipo: App da Web
 *        - Executar como: Eu
 *        - Quem pode acessar: Qualquer pessoa
 *   5. Copie a URL gerada e cole no campo "URL da API" do portal
 */

// Deixe vazio para usar a planilha onde o script está instalado.
var PLANILHA_ID = '';

var SENHA_SALT = 'imaculados-mc-salt';       // troque por um texto secreto seu
var HORAS_SESSAO = 12;

// ---------------------------------------------------------------------------
// Estrutura das abas
// ---------------------------------------------------------------------------
var ABAS = {
  Integrantes: ['id','nome','apelido','cargo','status','telefone','email','data_nascimento',
                'data_entrada','moto_modelo','moto_placa','tipo_sanguineo','contato_emergencia','observacoes'],
  Usuarios:    ['id','integrante_id','login','senha_hash','cargo','ativo','permissoes_customizadas'],
  Mensalidades:['id','integrante_id','referencia','vencimento','valor','pago','data_pagamento','forma_pagamento'],
  Eventos:     ['id','nome','data','local','descricao','tipo','status','criador_id'],
  Presencas:   ['id','evento_id','integrante_id','confirmacao'],
  Comunicados: ['id','titulo','mensagem','fixado','data','autor_id'],
  Solicitacoes:['id','nome','apelido_desejado','telefone','email','data_nascimento','moto_modelo',
                'mensagem','status','data_solicitacao','integrante_criado_id'],
  Caixa:       ['id','tipo','descricao','valor','data'],
  Sessoes:     ['token','usuario_id','expira_em']
};

var CARGOS = ['Presidente','Vice-Presidente','Diretor','Tesoureiro','Disciplina','Integrante','Prospero'];

var CATALOGO_PERMISSOES = [
  {chave:'ver_dashboard', label:'Ver o dashboard', grupo:'Geral'},
  {chave:'ver_integrantes', label:'Ver a lista de integrantes', grupo:'Integrantes'},
  {chave:'editar_integrantes', label:'Cadastrar e editar integrantes', grupo:'Integrantes'},
  {chave:'excluir_integrantes', label:'Excluir integrantes', grupo:'Integrantes'},
  {chave:'ver_financeiro', label:'Ver mensalidades e caixa', grupo:'Financeiro'},
  {chave:'editar_financeiro', label:'Lançar mensalidades e registrar pagamentos', grupo:'Financeiro'},
  {chave:'ver_eventos', label:'Ver eventos e confirmar presença', grupo:'Eventos'},
  {chave:'editar_eventos', label:'Criar, editar e excluir eventos', grupo:'Eventos'},
  {chave:'ver_comunicados', label:'Ver comunicados', grupo:'Comunicados'},
  {chave:'editar_comunicados', label:'Publicar e excluir comunicados', grupo:'Comunicados'},
  {chave:'ver_documentos', label:'Ver e baixar documentos', grupo:'Documentos'},
  {chave:'editar_documentos', label:'Enviar e excluir documentos', grupo:'Documentos'},
  {chave:'ver_solicitacoes', label:'Ver solicitações de ingresso', grupo:'Solicitações'},
  {chave:'analisar_solicitacoes', label:'Aprovar e recusar solicitações', grupo:'Solicitações'},
  {chave:'gerenciar_acessos', label:'Gerenciar acessos e permissões', grupo:'Administração'}
];
var TODAS_PERMISSOES = CATALOGO_PERMISSOES.map(function(p){ return p.chave; });

var BASICO = ['ver_dashboard','ver_eventos','ver_comunicados'];
var INTEGRANTE_PERM = BASICO.concat(['ver_integrantes','ver_documentos']);
var DIRETORIA_PERM = INTEGRANTE_PERM.concat(['editar_integrantes','ver_financeiro','editar_eventos',
  'editar_comunicados','editar_documentos','ver_solicitacoes','analisar_solicitacoes']);

var PADROES_POR_CARGO = {
  'Presidente': TODAS_PERMISSOES.slice(),
  'Vice-Presidente': DIRETORIA_PERM.slice(),
  'Diretor': DIRETORIA_PERM.slice(),
  'Tesoureiro': INTEGRANTE_PERM.concat(['ver_financeiro','editar_financeiro','editar_documentos']),
  'Disciplina': INTEGRANTE_PERM.concat(['editar_comunicados']),
  'Integrante': INTEGRANTE_PERM.slice(),
  'Prospero': BASICO.slice()
};

// ---------------------------------------------------------------------------
// Instalação
// ---------------------------------------------------------------------------
function planilha() {
  return PLANILHA_ID ? SpreadsheetApp.openById(PLANILHA_ID) : SpreadsheetApp.getActiveSpreadsheet();
}

/**
 * Cria as abas que faltarem (sem apagar nada do que já existe) e, se ainda não
 * houver nenhum acesso cadastrado, cria o login inicial de Presidente.
 */
function prepararPlanilha() {
  var ss = planilha();
  Object.keys(ABAS).forEach(function(nome) {
    var aba = ss.getSheetByName(nome);
    if (!aba) {
      aba = ss.insertSheet(nome);
      aba.appendRow(ABAS[nome]);
      aba.getRange(1, 1, 1, ABAS[nome].length).setFontWeight('bold');
      aba.setFrozenRows(1);
    } else if (aba.getLastRow() === 0) {
      aba.appendRow(ABAS[nome]);
    }
  });

  var usuarios = lerAba('Usuarios');
  if (usuarios.length === 0) {
    var integrantes = lerAba('Integrantes');
    var idIntegrante;
    if (integrantes.length > 0) {
      idIntegrante = integrantes[0].id;                 // usa o 1º da planilha
      atualizarLinha('Integrantes', integrantes[0]._linha, {cargo: 'Presidente'});
    } else {
      idIntegrante = inserir('Integrantes', {
        nome: 'Presidente Imaculados', apelido: 'Presidente',
        cargo: 'Presidente', status: 'Ativo', data_entrada: hoje()
      });
    }
    inserir('Usuarios', {
      integrante_id: idIntegrante, login: 'presidente',
      senha_hash: hashSenha('imaculados123'), cargo: 'Presidente', ativo: true
    });
    Logger.log('Acesso inicial criado -> login: presidente | senha: imaculados123');
    Logger.log('IMPORTANTE: troque essa senha no portal assim que entrar.');
  } else {
    Logger.log('Abas conferidas. Já existem acessos cadastrados.');
  }
}

// ---------------------------------------------------------------------------
// Utilidades de planilha
// ---------------------------------------------------------------------------
function aba(nome) {
  var s = planilha().getSheetByName(nome);
  if (!s) throw new Error('Aba não encontrada: ' + nome + '. Execute prepararPlanilha().');
  return s;
}

function lerAba(nome) {
  var s = aba(nome);
  var ultima = s.getLastRow();
  if (ultima < 2) return [];
  var cabecalho = s.getRange(1, 1, 1, s.getLastColumn()).getValues()[0];
  var valores = s.getRange(2, 1, ultima - 1, s.getLastColumn()).getValues();
  return valores.map(function(linha, idx) {
    var obj = {_linha: idx + 2};
    cabecalho.forEach(function(campo, c) {
      if (campo) obj[String(campo)] = normalizar(linha[c]);
    });
    return obj;
  }).filter(function(o){ return o.id !== '' && o.id !== null && o.id !== undefined; });
}

function normalizar(v) {
  if (v instanceof Date) return Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  if (v === 'TRUE' || v === true) return true;
  if (v === 'FALSE' || v === false) return false;
  return v;
}

function proximoId(nome) {
  var linhas = lerAba(nome);
  var max = 0;
  linhas.forEach(function(l) { var n = Number(l.id) || 0; if (n > max) max = n; });
  return max + 1;
}

function inserir(nome, dados) {
  var s = aba(nome);
  var cabecalho = s.getRange(1, 1, 1, s.getLastColumn()).getValues()[0];
  var id = dados.id || proximoId(nome);
  dados.id = id;
  var linha = cabecalho.map(function(campo) {
    var v = dados[campo];
    return (v === undefined || v === null) ? '' : v;
  });
  s.appendRow(linha);
  return id;
}

function atualizarLinha(nome, numeroLinha, mudancas) {
  var s = aba(nome);
  var cabecalho = s.getRange(1, 1, 1, s.getLastColumn()).getValues()[0];
  cabecalho.forEach(function(campo, c) {
    if (mudancas.hasOwnProperty(campo)) {
      s.getRange(numeroLinha, c + 1).setValue(mudancas[campo]);
    }
  });
}

function acharPorId(nome, id) {
  var alvo = String(id);
  var achados = lerAba(nome).filter(function(l){ return String(l.id) === alvo; });
  return achados.length ? achados[0] : null;
}

function excluirPorId(nome, id) {
  var reg = acharPorId(nome, id);
  if (reg) aba(nome).deleteRow(reg._linha);
  return !!reg;
}

function hoje() {
  return Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
}
function agora() {
  return Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd'T'HH:mm:ss");
}

// ---------------------------------------------------------------------------
// Senhas, sessões e permissões
// ---------------------------------------------------------------------------
function hashSenha(senha) {
  var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, senha + SENHA_SALT);
  return bytes.map(function(b) {
    return ('0' + (b < 0 ? b + 256 : b).toString(16)).slice(-2);
  }).join('');
}

function criarSessao(usuarioId) {
  var token = Utilities.getUuid();
  var expira = new Date(Date.now() + HORAS_SESSAO * 3600 * 1000);
  aba('Sessoes').appendRow([token, usuarioId, Utilities.formatDate(expira, Session.getScriptTimeZone(), "yyyy-MM-dd'T'HH:mm:ss")]);
  return token;
}

function usuarioDaSessao(token) {
  if (!token) return null;
  var sessoes = lerAbaSessoes();
  for (var i = 0; i < sessoes.length; i++) {
    if (sessoes[i].token === token) {
      if (new Date(sessoes[i].expira_em) < new Date()) return null;
      return acharPorId('Usuarios', sessoes[i].usuario_id);
    }
  }
  return null;
}

function lerAbaSessoes() {
  var s = aba('Sessoes');
  var ultima = s.getLastRow();
  if (ultima < 2) return [];
  return s.getRange(2, 1, ultima - 1, 3).getValues().map(function(l) {
    return {token: String(l[0]), usuario_id: l[1], expira_em: normalizar(l[2])};
  });
}

function permissoesEfetivas(cargo, customizadasJson) {
  var set = {};
  (PADROES_POR_CARGO[cargo] || BASICO).forEach(function(c){ set[c] = true; });
  var custom = {};
  try { custom = customizadasJson ? JSON.parse(customizadasJson) : {}; } catch (e) { custom = {}; }
  Object.keys(custom).forEach(function(c) {
    if (TODAS_PERMISSOES.indexOf(c) === -1) return;
    if (custom[c]) set[c] = true; else delete set[c];
  });
  return Object.keys(set);
}

function permissoesDoUsuario(u) {
  return permissoesEfetivas(u.cargo, u.permissoes_customizadas);
}

function exigir(usuario, chave) {
  if (!usuario) throw {status: 401, mensagem: 'Sessão expirada. Faça login novamente.'};
  if (permissoesDoUsuario(usuario).indexOf(chave) === -1) {
    throw {status: 403, mensagem: 'Você não tem permissão para acessar este recurso'};
  }
}

// ---------------------------------------------------------------------------
// Entrada HTTP
// ---------------------------------------------------------------------------
function doGet(e) {
  return json({status: 'online', sistema: 'Portal Imaculados M.C. (Google Planilhas)'});
}

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);   // evita duas gravações simultâneas na mesma linha
  } catch (err) {
    return json({detail: 'Servidor ocupado, tente novamente.'}, 503);
  }
  try {
    var req = JSON.parse(e.postData.contents);
    var resultado = rotear(req.path || '/', (req.method || 'GET').toUpperCase(), req.body || {}, req.token);
    return json(resultado);
  } catch (err) {
    var status = err && err.status ? err.status : 500;
    var msg = err && err.mensagem ? err.mensagem : (err && err.message ? err.message : 'Erro inesperado');
    return json({detail: msg}, status);
  } finally {
    lock.releaseLock();
  }
}

function json(obj, status) {
  if (status && status >= 400) obj._status = status;
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// ---------------------------------------------------------------------------
// Roteador
// ---------------------------------------------------------------------------
function rotear(path, metodo, body, token) {
  var u = usuarioDaSessao(token);
  var partes = path.split('?')[0].split('/').filter(String);

  // ---- público ----
  if (path === '/auth/login' && metodo === 'POST') return login(body);
  if (partes[0] === 'solicitacoes' && partes.length === 1 && metodo === 'POST') return criarSolicitacao(body);

  // ---- autenticado ----
  if (path === '/auth/me') { if (!u) throw {status:401, mensagem:'Sessão expirada'}; return meuPerfil(u); }
  if (path === '/dashboard') { exigir(u, 'ver_dashboard'); return dashboard(); }

  if (partes[0] === 'integrantes') {
    if (partes.length === 1 && metodo === 'GET')  { exigir(u,'ver_integrantes'); return lerAba('Integrantes'); }
    if (partes.length === 1 && metodo === 'POST') { exigir(u,'editar_integrantes'); return criarIntegrante(body); }
    if (partes.length === 2 && metodo === 'PUT')  { exigir(u,'editar_integrantes'); return editarIntegrante(partes[1], body); }
    if (partes.length === 2 && metodo === 'DELETE'){ exigir(u,'excluir_integrantes'); return excluirIntegrante(partes[1]); }
    if (partes.length === 3 && partes[2] === 'criar-acesso' && metodo === 'POST') {
      exigir(u,'gerenciar_acessos'); return criarAcesso(partes[1]);
    }
  }

  if (partes[0] === 'mensalidades') {
    if (partes.length === 1 && metodo === 'GET')  { exigir(u,'ver_financeiro'); return listarMensalidades(); }
    if (partes.length === 1 && metodo === 'POST') { exigir(u,'editar_financeiro'); return criarMensalidade(body); }
    if (partes.length === 3 && partes[2] === 'pagar') { exigir(u,'editar_financeiro'); return pagarMensalidade(partes[1], body); }
  }

  if (partes[0] === 'eventos') {
    if (partes.length === 1 && metodo === 'GET')  { exigir(u,'ver_eventos'); return listarEventos(); }
    if (partes.length === 1 && metodo === 'POST') { exigir(u,'editar_eventos'); return criarEvento(body, u); }
    if (partes.length === 2 && metodo === 'PUT')  { exigir(u,'editar_eventos'); return editarEvento(partes[1], body); }
    if (partes.length === 2 && metodo === 'DELETE'){ exigir(u,'editar_eventos'); return excluirEvento(partes[1]); }
    if (partes.length === 3 && partes[2] === 'presencas') { exigir(u,'ver_eventos'); return listarPresencas(partes[1]); }
    if (partes.length === 3 && partes[2] === 'presenca')  { exigir(u,'ver_eventos'); return confirmarPresenca(partes[1], body, u); }
  }

  if (partes[0] === 'comunicados') {
    if (partes.length === 1 && metodo === 'GET')  { exigir(u,'ver_comunicados'); return listarComunicados(); }
    if (partes.length === 1 && metodo === 'POST') { exigir(u,'editar_comunicados'); return criarComunicado(body, u); }
    if (partes.length === 2 && metodo === 'DELETE'){ exigir(u,'editar_comunicados'); return excluirRegistro('Comunicados', partes[1]); }
  }

  if (partes[0] === 'solicitacoes') {
    if (partes.length === 1 && metodo === 'GET') { exigir(u,'ver_solicitacoes'); return lerAba('Solicitacoes'); }
    if (partes.length === 3 && partes[2] === 'aprovar') { exigir(u,'analisar_solicitacoes'); return aprovarSolicitacao(partes[1]); }
    if (partes.length === 3 && partes[2] === 'recusar') { exigir(u,'analisar_solicitacoes'); return recusarSolicitacao(partes[1]); }
  }

  if (partes[0] === 'usuarios') {
    exigir(u, 'gerenciar_acessos');
    if (partes.length === 1 && metodo === 'GET') return listarUsuarios();
    if (partes.length === 2 && metodo === 'PATCH') return atualizarUsuario(partes[1], body);
    if (partes.length === 3 && partes[2] === 'permissoes' && metodo === 'PUT') return atualizarPermissoes(partes[1], body);
    if (partes.length === 3 && partes[2] === 'resetar-senha') return resetarSenha(partes[1]);
  }

  if (path === '/permissoes/catalogo') {
    exigir(u, 'gerenciar_acessos');
    return {permissoes: CATALOGO_PERMISSOES, cargos: CARGOS, padroes_por_cargo: PADROES_POR_CARGO};
  }

  throw {status: 404, mensagem: 'Rota não encontrada: ' + metodo + ' ' + path};
}

// ---------------------------------------------------------------------------
// Autenticação
// ---------------------------------------------------------------------------
function login(body) {
  var alvo = String(body.login || '').trim().toLowerCase();
  var usuarios = lerAba('Usuarios');
  for (var i = 0; i < usuarios.length; i++) {
    var u = usuarios[i];
    if (String(u.login).trim().toLowerCase() !== alvo) continue;
    if (u.ativo === false) throw {status: 401, mensagem: 'Este acesso está bloqueado'};
    if (String(u.senha_hash) !== hashSenha(String(body.senha || ''))) break;

    var integrante = u.integrante_id ? acharPorId('Integrantes', u.integrante_id) : null;
    return {
      access_token: criarSessao(u.id),
      token_type: 'bearer',
      cargo: u.cargo,
      nome: integrante ? integrante.nome : u.login,
      permissoes: permissoesDoUsuario(u)
    };
  }
  throw {status: 401, mensagem: 'Usuário ou senha inválidos'};
}

function meuPerfil(u) {
  var i = u.integrante_id ? acharPorId('Integrantes', u.integrante_id) : null;
  return {id: u.id, login: u.login, nome: i ? i.nome : u.login, cargo: u.cargo, permissoes: permissoesDoUsuario(u)};
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
function dashboard() {
  var integrantes = lerAba('Integrantes');
  var mensalidades = lerAba('Mensalidades');
  var eventos = lerAba('Eventos');
  var comunicados = lerAba('Comunicados');
  var caixa = lerAba('Caixa');

  var ativos = integrantes.filter(function(i){ return i.status === 'Ativo'; }).length;
  var pagas = mensalidades.filter(function(m){ return m.pago === true; }).length;
  var pct = mensalidades.length ? Math.round(pagas / mensalidades.length * 1000) / 10 : 0;

  var saldo = 0;
  caixa.forEach(function(l) {
    var v = Number(l.valor) || 0;
    saldo += (String(l.tipo).indexOf('Sa') === 0) ? -v : v;   // Saída x Entrada
  });

  var futuros = eventos.filter(function(e){ return e.data && String(e.data) >= hoje(); })
                       .sort(function(a,b){ return String(a.data) < String(b.data) ? -1 : 1; });

  var mesAtual = hoje().slice(5, 7);
  var aniversariantes = integrantes.filter(function(i) {
    return i.data_nascimento && String(i.data_nascimento).slice(5, 7) === mesAtual && i.status === 'Ativo';
  }).map(function(i) {
    return {id: i.id, nome: i.nome, apelido: i.apelido, data_nascimento: i.data_nascimento};
  });

  var ultimos = comunicados.slice().sort(function(a, b) {
    if (!!a.fixado !== !!b.fixado) return a.fixado ? -1 : 1;
    return String(b.data) < String(a.data) ? -1 : 1;
  }).slice(0, 3).map(function(c) {
    var autor = c.autor_id ? acharPorId('Integrantes', c.autor_id) : null;
    return {id: c.id, titulo: c.titulo, data: c.data, autor_nome: autor ? autor.nome : null};
  });

  return {
    total_integrantes: ativos,
    percentual_mensalidades_pagas: pct,
    saldo_caixa: saldo,
    proximo_evento_nome: futuros.length ? futuros[0].nome : null,
    proximo_evento_data: futuros.length ? futuros[0].data : null,
    aniversariantes_mes: aniversariantes,
    ultimos_comunicados: ultimos
  };
}

// ---------------------------------------------------------------------------
// Integrantes
// ---------------------------------------------------------------------------
function criarIntegrante(body) {
  body.data_entrada = body.data_entrada || hoje();
  body.status = body.status || 'Ativo';
  body.cargo = body.cargo || 'Integrante';
  var id = inserir('Integrantes', body);
  return acharPorId('Integrantes', id);
}

function editarIntegrante(id, body) {
  var reg = acharPorId('Integrantes', id);
  if (!reg) throw {status: 404, mensagem: 'Integrante não encontrado'};
  atualizarLinha('Integrantes', reg._linha, body);

  // o cargo controla as permissões: espelha no acesso, se houver
  if (body.cargo) {
    var acesso = lerAba('Usuarios').filter(function(x){ return String(x.integrante_id) === String(id); })[0];
    if (acesso) atualizarLinha('Usuarios', acesso._linha, {cargo: body.cargo});
  }
  return acharPorId('Integrantes', id);
}

function excluirIntegrante(id) {
  var acesso = lerAba('Usuarios').filter(function(x){ return String(x.integrante_id) === String(id); })[0];
  if (acesso) aba('Usuarios').deleteRow(acesso._linha);
  if (!excluirPorId('Integrantes', id)) throw {status: 404, mensagem: 'Integrante não encontrado'};
  return {detail: 'Integrante excluído'};
}

// ---------------------------------------------------------------------------
// Mensalidades
// ---------------------------------------------------------------------------
function listarMensalidades() {
  return lerAba('Mensalidades').map(function(m) {
    var i = acharPorId('Integrantes', m.integrante_id);
    m.integrante_nome = i ? i.nome : null;
    return m;
  });
}

function criarMensalidade(body) {
  body.valor = body.valor || 40;
  body.pago = false;
  var id = inserir('Mensalidades', body);
  return acharPorId('Mensalidades', id);
}

function pagarMensalidade(id, body) {
  var m = acharPorId('Mensalidades', id);
  if (!m) throw {status: 404, mensagem: 'Mensalidade não encontrada'};
  var data = body.data_pagamento || hoje();
  atualizarLinha('Mensalidades', m._linha, {
    pago: true, data_pagamento: data, forma_pagamento: body.forma_pagamento || 'Pix'
  });
  var i = acharPorId('Integrantes', m.integrante_id);
  inserir('Caixa', {
    tipo: 'Entrada',
    descricao: 'Mensalidade ' + m.referencia + ' - ' + (i ? i.nome : '#' + m.integrante_id),
    valor: m.valor, data: data
  });
  return acharPorId('Mensalidades', id);
}

// ---------------------------------------------------------------------------
// Eventos e presenças
// ---------------------------------------------------------------------------
function listarEventos() {
  var presencas = lerAba('Presencas');
  return lerAba('Eventos').map(function(e) {
    e.total_confirmados = presencas.filter(function(p) {
      return String(p.evento_id) === String(e.id) && p.confirmacao === 'Confirmado';
    }).length;
    return e;
  });
}

function criarEvento(body, u) {
  body.status = body.status || 'Planejado';
  body.tipo = body.tipo || 'Encontro';
  body.criador_id = u.integrante_id;
  var id = inserir('Eventos', body);
  return acharPorId('Eventos', id);
}

function editarEvento(id, body) {
  var e = acharPorId('Eventos', id);
  if (!e) throw {status: 404, mensagem: 'Evento não encontrado'};
  atualizarLinha('Eventos', e._linha, body);
  return acharPorId('Eventos', id);
}

function excluirEvento(id) {
  lerAba('Presencas').filter(function(p){ return String(p.evento_id) === String(id); })
    .sort(function(a,b){ return b._linha - a._linha; })      // de baixo p/ cima: não desloca as demais
    .forEach(function(p){ aba('Presencas').deleteRow(p._linha); });
  if (!excluirPorId('Eventos', id)) throw {status: 404, mensagem: 'Evento não encontrado'};
  return {detail: 'Evento excluído'};
}

function listarPresencas(eventoId) {
  return lerAba('Presencas').filter(function(p) {
    return String(p.evento_id) === String(eventoId);
  }).map(function(p) {
    var i = acharPorId('Integrantes', p.integrante_id);
    p.integrante_nome = i ? i.nome : null;
    return p;
  });
}

function confirmarPresenca(eventoId, body, u) {
  var existente = lerAba('Presencas').filter(function(p) {
    return String(p.evento_id) === String(eventoId) && String(p.integrante_id) === String(u.integrante_id);
  })[0];
  if (existente) {
    atualizarLinha('Presencas', existente._linha, {confirmacao: body.confirmacao});
    return acharPorId('Presencas', existente.id);
  }
  var id = inserir('Presencas', {
    evento_id: eventoId, integrante_id: u.integrante_id, confirmacao: body.confirmacao
  });
  return acharPorId('Presencas', id);
}

// ---------------------------------------------------------------------------
// Comunicados
// ---------------------------------------------------------------------------
function listarComunicados() {
  return lerAba('Comunicados').map(function(c) {
    var a = c.autor_id ? acharPorId('Integrantes', c.autor_id) : null;
    c.autor_nome = a ? a.nome : null;
    return c;
  });
}

function criarComunicado(body, u) {
  body.data = agora();
  body.autor_id = u.integrante_id;
  body.fixado = !!body.fixado;
  var id = inserir('Comunicados', body);
  return acharPorId('Comunicados', id);
}

function excluirRegistro(nomeAba, id) {
  if (!excluirPorId(nomeAba, id)) throw {status: 404, mensagem: 'Registro não encontrado'};
  return {detail: 'Registro excluído'};
}

// ---------------------------------------------------------------------------
// Solicitações de ingresso
// ---------------------------------------------------------------------------
function criarSolicitacao(body) {
  if (!body.nome || !body.telefone) throw {status: 400, mensagem: 'Informe nome e telefone'};
  body.status = 'Pendente';
  body.data_solicitacao = agora();
  var id = inserir('Solicitacoes', body);
  return acharPorId('Solicitacoes', id);
}

function aprovarSolicitacao(id) {
  var s = acharPorId('Solicitacoes', id);
  if (!s) throw {status: 404, mensagem: 'Solicitação não encontrada'};
  if (s.status !== 'Pendente') throw {status: 400, mensagem: 'Esta solicitação já foi analisada'};

  var idIntegrante = inserir('Integrantes', {
    nome: s.nome, apelido: s.apelido_desejado, cargo: 'Prospero', status: 'Ativo',
    telefone: s.telefone, email: s.email, data_nascimento: s.data_nascimento,
    moto_modelo: s.moto_modelo, data_entrada: hoje()
  });

  var login = gerarLogin(s.nome);
  var senha = senhaTemporaria();
  inserir('Usuarios', {
    integrante_id: idIntegrante, login: login,
    senha_hash: hashSenha(senha), cargo: 'Prospero', ativo: true
  });

  atualizarLinha('Solicitacoes', s._linha, {status: 'Aprovada', integrante_criado_id: idIntegrante});
  return {integrante_id: idIntegrante, login_gerado: login, senha_temporaria: senha};
}

function recusarSolicitacao(id) {
  var s = acharPorId('Solicitacoes', id);
  if (!s) throw {status: 404, mensagem: 'Solicitação não encontrada'};
  if (s.status !== 'Pendente') throw {status: 400, mensagem: 'Esta solicitação já foi analisada'};
  atualizarLinha('Solicitacoes', s._linha, {status: 'Recusada'});
  return acharPorId('Solicitacoes', id);
}

function gerarLogin(nome) {
  var limpo = String(nome).toLowerCase()
    .normalize ? String(nome).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '') : String(nome).toLowerCase();
  var partes = limpo.replace(/[^a-z ]/g, '').split(' ').filter(String);
  var base = (partes[0] || 'integrante') + (partes.length > 1 ? partes[partes.length - 1] : '');
  var existentes = lerAba('Usuarios').map(function(u){ return String(u.login); });
  var login = base, n = 1;
  while (existentes.indexOf(login) > -1) { n++; login = base + n; }
  return login;
}

function senhaTemporaria() {
  return Utilities.getUuid().replace(/-/g, '').slice(0, 8);
}

// ---------------------------------------------------------------------------
// Usuários, acessos e permissões
// ---------------------------------------------------------------------------
function listarUsuarios() {
  return lerAba('Usuarios').map(function(u) {
    var i = u.integrante_id ? acharPorId('Integrantes', u.integrante_id) : null;
    var custom = {};
    try { custom = u.permissoes_customizadas ? JSON.parse(u.permissoes_customizadas) : {}; } catch (e) {}
    return {
      id: u.id, login: u.login, cargo: u.cargo, ativo: u.ativo !== false,
      integrante_id: u.integrante_id, integrante_nome: i ? i.nome : null,
      permissoes_efetivas: permissoesDoUsuario(u),
      permissoes_customizadas: custom
    };
  });
}

function restariaAdministrador(idIgnorado) {
  return lerAba('Usuarios').some(function(u) {
    if (String(u.id) === String(idIgnorado)) return false;
    return u.ativo !== false && permissoesDoUsuario(u).indexOf('gerenciar_acessos') > -1;
  });
}

function atualizarUsuario(id, body) {
  var u = acharPorId('Usuarios', id);
  if (!u) throw {status: 404, mensagem: 'Usuário não encontrado'};

  var simulado = {
    cargo: body.cargo !== undefined ? body.cargo : u.cargo,
    ativo: body.ativo !== undefined ? body.ativo : (u.ativo !== false),
    permissoes_customizadas: u.permissoes_customizadas
  };
  var continuaAdmin = simulado.ativo && permissoesDoUsuario(simulado).indexOf('gerenciar_acessos') > -1;
  if (!continuaAdmin && !restariaAdministrador(id)) {
    throw {status: 400, mensagem: 'Esta alteração deixaria o sistema sem nenhum administrador ativo'};
  }

  var mudancas = {};
  if (body.cargo !== undefined) {
    if (CARGOS.indexOf(body.cargo) === -1) throw {status: 400, mensagem: 'Cargo inválido'};
    mudancas.cargo = body.cargo;
    var i = u.integrante_id ? acharPorId('Integrantes', u.integrante_id) : null;
    if (i) atualizarLinha('Integrantes', i._linha, {cargo: body.cargo});
  }
  if (body.ativo !== undefined) mudancas.ativo = body.ativo;
  atualizarLinha('Usuarios', u._linha, mudancas);

  return listarUsuarios().filter(function(x){ return String(x.id) === String(id); })[0];
}

function atualizarPermissoes(id, body) {
  var u = acharPorId('Usuarios', id);
  if (!u) throw {status: 404, mensagem: 'Usuário não encontrado'};

  var limpos = {};
  Object.keys(body.permissoes || {}).forEach(function(c) {
    if (TODAS_PERMISSOES.indexOf(c) === -1) throw {status: 400, mensagem: 'Permissão inválida: ' + c};
    limpos[c] = !!body.permissoes[c];
  });

  var simulado = {cargo: u.cargo, ativo: u.ativo !== false, permissoes_customizadas: JSON.stringify(limpos)};
  var continuaAdmin = simulado.ativo && permissoesDoUsuario(simulado).indexOf('gerenciar_acessos') > -1;
  if (!continuaAdmin && !restariaAdministrador(id)) {
    throw {status: 400, mensagem: 'Esta alteração deixaria o sistema sem nenhum administrador ativo'};
  }

  atualizarLinha('Usuarios', u._linha, {
    permissoes_customizadas: Object.keys(limpos).length ? JSON.stringify(limpos) : ''
  });
  return listarUsuarios().filter(function(x){ return String(x.id) === String(id); })[0];
}

function resetarSenha(id) {
  var u = acharPorId('Usuarios', id);
  if (!u) throw {status: 404, mensagem: 'Usuário não encontrado'};
  var senha = senhaTemporaria();
  atualizarLinha('Usuarios', u._linha, {senha_hash: hashSenha(senha)});
  return {login: u.login, senha_temporaria: senha};
}

function criarAcesso(integranteId) {
  var i = acharPorId('Integrantes', integranteId);
  if (!i) throw {status: 404, mensagem: 'Integrante não encontrado'};
  var jaTem = lerAba('Usuarios').filter(function(x){ return String(x.integrante_id) === String(integranteId); })[0];
  if (jaTem) throw {status: 400, mensagem: 'Este integrante já possui acesso'};

  var login = gerarLogin(i.nome);
  var senha = senhaTemporaria();
  var id = inserir('Usuarios', {
    integrante_id: integranteId, login: login, senha_hash: hashSenha(senha),
    cargo: i.cargo || 'Integrante', ativo: true
  });
  return {usuario_id: id, login: login, senha_temporaria: senha};
}
